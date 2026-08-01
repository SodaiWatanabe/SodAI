"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import {
  type BrainRangeOption,
  BrainRangeSlider,
} from "@/components/human/brain-range-slider";
import {
  type DiscreteRange,
  formatConditionRange,
  HUMAN_REASONING_EFFORT_ORDER,
  rangeIndices,
  valuesInRange,
} from "@/components/human/human-answer-condition-range";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import { reasoningEffortName } from "@/lib/chat/reasoning-effort";
import type {
  AvailableAnswerer,
  ReasoningEffort,
} from "@/lib/chat/types";
import type { HumanAnswerConditions } from "@/lib/human/types";

type ConditionSelectorProps = {
  disabled?: boolean;
  footer?: ReactNode;
  hint: ReactNode;
  label: string;
  lowerMaximum?: number;
  onChange: (range: DiscreteRange) => void;
  options: readonly BrainRangeOption[];
  upperMaximum?: number;
  value: DiscreteRange;
};

function ConditionSelector({
  disabled,
  footer,
  hint,
  label,
  lowerMaximum,
  onChange,
  options,
  upperMaximum,
  value,
}: ConditionSelectorProps) {
  const valueText = formatConditionRange(
    options.map((option) => option.label),
    value,
  );

  return (
    <Popover placement="bottom-end" gutter={6}>
      <PopoverTrigger
        disabled={disabled}
        aria-label={`${label}: ${valueText}`}
        className="group flex h-11 w-full items-center gap-2 rounded-xl px-3 text-sm transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] disabled:cursor-default disabled:opacity-50"
      >
        <span className="shrink-0 text-[var(--muted)]">{label}</span>
        <span className="min-w-0 flex-1 truncate text-right font-medium text-[var(--text)]">
          {valueText}
        </span>
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 shrink-0 text-[var(--muted)] transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>
      <PopoverContent
        role="group"
        aria-label={`${label}の範囲`}
        className="w-52 p-4"
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[var(--muted)]">
            {label}
          </span>
          <HelpTooltip label={`${label}のヒント`}>{hint}</HelpTooltip>
        </div>
        <BrainRangeSlider
          disabled={disabled}
          label={label}
          lowerMaximum={lowerMaximum}
          options={options}
          upperMaximum={upperMaximum}
          value={value}
          onChange={onChange}
        />
        {footer ? (
          <p className="mt-3 border-t border-[var(--divider)] pt-3 text-sm leading-5 text-[var(--muted)]">
            {footer}
          </p>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

function reasoningMaximumIndex(
  answerer: AvailableAnswerer,
  options: readonly BrainRangeOption[],
): number {
  return Math.max(
    ...answerer.reasoning_efforts.map((effort) =>
      options.findIndex((option) => option.id === effort.id),
    ),
  );
}

function rankUpgradeNotice(rankName: string): string | null {
  if (rankName === "Human Lite") {
    return "Standard、Proを選択するには、ランクを上げる必要があります。";
  }
  if (rankName === "Human Standard") {
    return "Proを選択するには、ランクを上げる必要があります。";
  }
  return null;
}

export function BrainAnswerConditionSelectors({
  answerers,
  availableAnswererIds,
  disabled = false,
  onChange,
  rankName,
  value,
}: {
  answerers: AvailableAnswerer[];
  availableAnswererIds: string[];
  disabled?: boolean;
  onChange: (conditions: HumanAnswerConditions) => void;
  rankName: string;
  value: HumanAnswerConditions;
}) {
  const answererOptions = answerers.map((answerer) => ({
    id: answerer.id,
    label: answerer.name.replace(/^Human\s+/, ""),
  }));
  const availableAnswererRange = rangeIndices(
    answererOptions.map((option) => option.id),
    availableAnswererIds,
  );
  const reasoningOptions = HUMAN_REASONING_EFFORT_ORDER.map((effort) => ({
    id: effort,
    label: reasoningEffortName(effort),
  }));
  const answererRange = rangeIndices(
    answererOptions.map((option) => option.id),
    value.answerer_ids,
  );
  const reasoningRange = rangeIndices(
    reasoningOptions.map((option) => option.id),
    value.reasoning_efforts,
  );
  const selectedAnswerers = answerers.slice(
    answererRange.lower,
    answererRange.upper + 1,
  );
  const selectedReasoningMaxima = selectedAnswerers.map((answerer) =>
    reasoningMaximumIndex(answerer, reasoningOptions),
  );
  const lowerEffortMaximum = Math.max(
    0,
    Math.min(...selectedReasoningMaxima),
  );
  const upperEffortMaximum = Math.max(0, ...selectedReasoningMaxima);
  const upgradeNotice = rankUpgradeNotice(rankName);

  function emit(
    nextAnswererRange: DiscreteRange,
    nextReasoningRange: DiscreteRange,
  ) {
    onChange({
      answerer_ids: valuesInRange(
        answererOptions.map((option) => option.id),
        nextAnswererRange,
      ),
      reasoning_efforts: valuesInRange(
        reasoningOptions.map((option) => option.id as ReasoningEffort),
        nextReasoningRange,
      ),
    });
  }

  function changeAnswererRange(nextRange: DiscreteRange) {
    const nextReasoningMaxima = answerers
      .slice(nextRange.lower, nextRange.upper + 1)
      .map((answerer) => reasoningMaximumIndex(answerer, reasoningOptions));
    const nextLowerMaximum = Math.max(0, Math.min(...nextReasoningMaxima));
    const nextUpperMaximum = Math.max(0, ...nextReasoningMaxima);
    const nextReasoningRange = {
      lower: Math.min(reasoningRange.lower, nextLowerMaximum),
      upper: Math.max(
        Math.min(reasoningRange.lower, nextLowerMaximum),
        Math.min(reasoningRange.upper, nextUpperMaximum),
      ),
    };
    emit(nextRange, nextReasoningRange);
  }

  return (
    <div className="grid gap-1 text-left">
      <ConditionSelector
        disabled={disabled}
        footer={upgradeNotice}
        hint={
          <p>
            Lite、Standard、Proの順で、期待される生成品質が上昇します。回答によって得られる報酬も大きくなります。
          </p>
        }
        label="要求モデル"
        lowerMaximum={availableAnswererRange.upper}
        options={answererOptions}
        upperMaximum={availableAnswererRange.upper}
        value={answererRange}
        onChange={changeAnswererRange}
      />
      <ConditionSelector
        disabled={disabled}
        hint={
          <div>
            <p>
              回答時間が以下のように割り当てられます。思考が深いほど、期待される生成品質が上昇します。回答によって得られる報酬も大きくなります。
            </p>
            <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 text-[var(--text)]">
              <dt>軽い</dt>
              <dd>2分</dd>
              <dt>中程度</dt>
              <dd>5分</dd>
              <dt>深い</dt>
              <dd>20分</dd>
              <dt>非常に深い</dt>
              <dd>1時間</dd>
            </dl>
          </div>
        }
        label="思考の深さ"
        lowerMaximum={lowerEffortMaximum}
        options={reasoningOptions}
        upperMaximum={upperEffortMaximum}
        value={reasoningRange}
        onChange={(nextRange) => emit(answererRange, nextRange)}
      />
    </div>
  );
}
