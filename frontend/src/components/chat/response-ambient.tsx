type ResponseAmbientProps = {
  active: boolean;
};

export function ResponseAmbient({ active }: ResponseAmbientProps) {
  return (
    <div
      aria-hidden="true"
      data-active={active ? "true" : "false"}
      className="response-ambient"
    >
      <span className="response-glow response-glow-one" />
      <span className="response-glow response-glow-two" />
      <span className="response-glow response-glow-three" />
    </div>
  );
}
