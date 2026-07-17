import { LockKeyhole, WifiOff } from "lucide-react";

interface PrivacyStatusProps {
  protocol: string | null;
}

export function PrivacyStatus({ protocol }: PrivacyStatusProps) {
  return (
    <div className="privacy-status" aria-label="Project privacy status">
      <span><LockKeyhole size={13} /> Vault unlocked</span>
      <span><WifiOff size={13} /> Network blocked</span>
      {protocol && <span className="protocol-label">Protocol {protocol}</span>}
    </div>
  );
}

