"""Open research exports with explicit provenance and no hidden network behavior."""

from __future__ import annotations

import uuid
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from lxml import etree

from .redaction import apply_confirmed_redactions


REFI_CODEBOOK_NS = "urn:QDA-XML:codebook:1.0"
ET.register_namespace("", REFI_CODEBOOK_NS)


def format_timestamp(milliseconds: int, *, decimal: str = ",") -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{decimal}{millis:03}"


def segments_to_srt(segments: list[dict], redactions: list[dict] | None = None) -> bytes:
    by_segment = _redactions_by_segment(redactions or [])
    blocks = []
    for index, segment in enumerate(segments, start=1):
        text = apply_confirmed_redactions(segment["text"], by_segment[segment["id"]])
        speaker = f'{segment["speaker"]}: ' if segment.get("speaker") else ""
        blocks.append(
            f"{index}\n{format_timestamp(segment['start_ms'])} --> {format_timestamp(segment['end_ms'])}\n{speaker}{text}"
        )
    return ("\n\n".join(blocks) + "\n").encode("utf-8")


def segments_to_vtt(segments: list[dict], redactions: list[dict] | None = None) -> bytes:
    body = segments_to_srt(segments, redactions).decode("utf-8")
    body = body.replace(",", ".")
    body = "\n\n".join("\n".join(block.splitlines()[1:]) for block in body.strip().split("\n\n"))
    return f"WEBVTT\n\n{body}\n".encode("utf-8")


def export_refi_codebook(codes: list[dict], *, origin: str = "TranscriptSeek 0.1.0") -> bytes:
    """Export a REFI-QDA Codebook 1.0 XML document (.qdc).

    Production release validation still requires the official XSD fixture; the
    structure and namespace follow the published 1.0 exchange specification.
    """
    namespace = f"{{{REFI_CODEBOOK_NS}}}"
    root = ET.Element(f"{namespace}CodeBook", {"origin": origin})
    container = ET.SubElement(root, f"{namespace}Codes")
    children: dict[str | None, list[dict]] = defaultdict(list)
    for code in codes:
        children[code.get("parent_id")].append(code)

    def append_code(parent: ET.Element, code: dict) -> None:
        guid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"transcriptseek:code:{code['id']}"))
        element = ET.SubElement(
            parent,
            f"{namespace}Code",
            {
                "guid": guid,
                "name": code["name"],
                "isCodable": "true",
                "color": f"#{code.get('color', '#6f7bf7').lstrip('#').upper()}",
            },
        )
        if code.get("description"):
            ET.SubElement(element, f"{namespace}Description").text = code["description"]
        for child in children.get(code["id"], []):
            append_code(element, child)

    for root_code in children[None]:
        append_code(container, root_code)
    ET.indent(root, space="  ")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    validate_refi_codebook(payload)
    return payload


def import_refi_codebook(payload: bytes) -> list[dict]:
    validate_refi_codebook(payload)
    root = ET.fromstring(payload)
    if root.tag != f"{{{REFI_CODEBOOK_NS}}}CodeBook":
        raise ValueError("Not a REFI-QDA Codebook 1.0 document")
    namespace = {"q": REFI_CODEBOOK_NS}
    result = []

    def read_code(element: ET.Element, parent_id: str | None) -> None:
        code_id = element.attrib["guid"]
        description = element.findtext("q:Description", default="", namespaces=namespace)
        result.append({
            "id": code_id,
            "parent_id": parent_id,
            "name": element.attrib["name"],
            "description": description,
            "color": f"#{element.attrib.get('color', '6F7BF7').lstrip('#')}",
        })
        for child in element.findall("q:Code", namespace):
            read_code(child, code_id)

    codes = root.find("q:Codes", namespace)
    if codes is None:
        raise ValueError("REFI-QDA Codebook is missing Codes")
    for element in codes.findall("q:Code", namespace):
        read_code(element, None)
    return result


def validate_refi_codebook(payload: bytes) -> None:
    schema_path = Path(__file__).with_name("schemas") / "Codebook.xsd"
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        schema = etree.XMLSchema(etree.parse(str(schema_path), parser))
        document = etree.fromstring(payload, parser)
        schema.assertValid(document)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as exc:
        raise ValueError(f"Invalid REFI-QDA Codebook 1.0: {exc}") from exc


def _redactions_by_segment(redactions: list[dict]) -> defaultdict[str, list[dict]]:
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for redaction in redactions:
        grouped[redaction["segment_id"]].append(redaction)
    return grouped
