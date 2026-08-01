"use client";

import {
  type KeyboardEvent,
  type PointerEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  type RangeBoundary,
  moveRangeBoundary,
  nearestRangeBoundary,
  rangeIndexFromPointer,
  rangePosition,
  rangeSelectionInsets,
} from "@/components/human/brain-range-slider-model";
import styles from "@/components/human/brain-range-slider.module.css";
import type { DiscreteRange } from "@/components/human/human-answer-condition-range";

export type BrainRangeOption = {
  id: string;
  label: string;
};

type BrainRangeSliderProps = {
  disabled?: boolean;
  label: string;
  lowerMaximum?: number;
  onChange: (range: DiscreteRange) => void;
  options: readonly BrainRangeOption[];
  upperMaximum?: number;
  value: DiscreteRange;
};

export function BrainRangeSlider({
  disabled = false,
  label,
  lowerMaximum,
  onChange,
  options,
  upperMaximum,
  value,
}: BrainRangeSliderProps) {
  const maximum = Math.max(0, options.length - 1);
  const sliderDisabled = disabled || maximum === 0;
  const limits = {
    lowerMaximum: lowerMaximum ?? maximum,
    upperMaximum: upperMaximum ?? maximum,
  };
  const selectionInsets = rangeSelectionInsets(value, maximum);
  const valueRef = useRef(value);
  const dragRef = useRef<{
    boundary: RangeBoundary;
    pointerId: number;
  } | null>(null);
  const [activeBoundary, setActiveBoundary] =
    useState<RangeBoundary>("upper");
  const [draggingBoundary, setDraggingBoundary] =
    useState<RangeBoundary | null>(null);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  function emit(nextValue: DiscreteRange) {
    valueRef.current = nextValue;
    onChange(nextValue);
  }

  function indexAtPointer(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return rangeIndexFromPointer(
      event.clientX,
      bounds.left,
      bounds.width,
      maximum,
    );
  }

  function movePointer(event: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    const movement = moveRangeBoundary(
      valueRef.current,
      drag.boundary,
      indexAtPointer(event),
      limits,
    );
    drag.boundary = movement.boundary;
    setActiveBoundary(movement.boundary);
    setDraggingBoundary(movement.boundary);
    emit(movement.range);
  }

  function finishPointer(event: PointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    setDraggingBoundary(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function moveWithKeyboard(
    event: KeyboardEvent<HTMLSpanElement>,
    boundary: RangeBoundary,
  ) {
    let nextIndex: number;
    const currentValue = boundary === "lower" ? value.lower : value.upper;

    switch (event.key) {
      case "ArrowDown":
      case "ArrowLeft":
        nextIndex = currentValue - 1;
        break;
      case "ArrowRight":
      case "ArrowUp":
        nextIndex = currentValue + 1;
        break;
      case "Home":
        nextIndex = boundary === "lower" ? 0 : value.lower;
        break;
      case "End":
        nextIndex =
          boundary === "lower"
            ? Math.min(value.upper, limits.lowerMaximum)
            : limits.upperMaximum;
        break;
      default:
        return;
    }

    event.preventDefault();
    setActiveBoundary(boundary);
    emit(
      boundary === "lower"
        ? {
            lower: Math.max(
              0,
              Math.min(nextIndex, value.upper, limits.lowerMaximum),
            ),
            upper: value.upper,
          }
        : {
            lower: value.lower,
            upper: Math.max(
              value.lower,
              Math.min(nextIndex, limits.upperMaximum),
            ),
          },
    );
  }

  return (
    <fieldset className={styles.fieldset} disabled={sliderDisabled}>
      <legend className="sr-only">{label}</legend>
      <div
        className={`${styles.root} ${
          draggingBoundary ? styles.rootDragging : ""
        }`}
        onPointerDown={(event) => {
          if (sliderDisabled || (event.pointerType === "mouse" && event.button !== 0)) {
            return;
          }

          event.preventDefault();
          const target = event.target as HTMLElement;
          const targetThumb = target.closest<HTMLElement>(
            "[data-range-boundary]",
          );
          const selectedIndex = indexAtPointer(event);
          const boundary =
            (targetThumb?.dataset.rangeBoundary as
              | RangeBoundary
              | undefined) ??
            nearestRangeBoundary(valueRef.current, selectedIndex);

          targetThumb?.focus({ preventScroll: true });
          setActiveBoundary(boundary);
          setDraggingBoundary(boundary);
          dragRef.current = { boundary, pointerId: event.pointerId };
          event.currentTarget.setPointerCapture(event.pointerId);

          const movement = moveRangeBoundary(
            valueRef.current,
            boundary,
            selectedIndex,
            limits,
          );
          dragRef.current.boundary = movement.boundary;
          setActiveBoundary(movement.boundary);
          setDraggingBoundary(movement.boundary);
          emit(movement.range);
        }}
        onPointerMove={movePointer}
        onPointerUp={finishPointer}
        onPointerCancel={finishPointer}
        onLostPointerCapture={(event) => {
          if (dragRef.current?.pointerId !== event.pointerId) return;
          dragRef.current = null;
          setDraggingBoundary(null);
        }}
      >
        <div className={styles.track}>
          {limits.upperMaximum > 0 ? (
            <div className={styles.selection} style={selectionInsets} />
          ) : null}
          {options.map((option, index) => (
            <span
              key={option.id}
              aria-hidden="true"
              className={`${styles.marker} ${
                index >= value.lower && index <= value.upper
                  ? styles.markerSelected
                  : ""
              }`}
              style={{ left: rangePosition(index, maximum) }}
            />
          ))}
        </div>
        <span
          role="slider"
          tabIndex={sliderDisabled ? -1 : 0}
          data-range-boundary="lower"
          aria-label={`${label}の下限`}
          aria-disabled={sliderDisabled}
          aria-valuemin={0}
          aria-valuemax={Math.min(value.upper, limits.lowerMaximum)}
          aria-valuenow={value.lower}
          aria-valuetext={options[value.lower]?.label}
          className={`${styles.thumb} ${
            activeBoundary === "lower" ? styles.thumbActive : ""
          } ${
            draggingBoundary === "lower" ? styles.thumbDragging : ""
          }`}
          style={{ left: rangePosition(value.lower, maximum) }}
          onKeyDown={(event) => moveWithKeyboard(event, "lower")}
        />
        <span
          role="slider"
          tabIndex={sliderDisabled ? -1 : 0}
          data-range-boundary="upper"
          aria-label={`${label}の上限`}
          aria-disabled={sliderDisabled}
          aria-valuemin={value.lower}
          aria-valuemax={limits.upperMaximum}
          aria-valuenow={value.upper}
          aria-valuetext={options[value.upper]?.label}
          className={`${styles.thumb} ${
            activeBoundary === "upper" ? styles.thumbActive : ""
          } ${
            draggingBoundary === "upper" ? styles.thumbDragging : ""
          }`}
          style={{ left: rangePosition(value.upper, maximum) }}
          onKeyDown={(event) => moveWithKeyboard(event, "upper")}
        />
      </div>
    </fieldset>
  );
}
