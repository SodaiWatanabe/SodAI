type IOSSpinnerProps = {
  label?: string;
};

export function IOSSpinner({ label = "読み込み中" }: IOSSpinnerProps) {
  return (
    <span role="status" aria-label={label} className="ios-spinner">
      {Array.from({ length: 12 }, (_, index) => (
        <span
          key={index}
          aria-hidden="true"
          className="ios-spinner-segment"
          style={{
            animationDelay: `${-1.1 + index / 12}s`,
            transform: `rotate(${index * 30}deg)`,
          }}
        />
      ))}
    </span>
  );
}
