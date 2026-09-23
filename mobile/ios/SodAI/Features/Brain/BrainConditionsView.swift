import SwiftUI

struct BrainConditionsView: View {
    @Environment(BrainStore.self) private var brain
    @Environment(ConversationStore.self) private var chat
    private var humans: [Answerer] { chat.answerers.filter { $0.kind == "human" && !$0.is_legacy } }
    private var selected: [Answerer] { humans.filter { brain.conditions.answerer_ids.contains($0.id) } }
    private var maxima: [Int] {
        selected.map {
            $0.reasoning_efforts.compactMap { BrainConditionRange.efforts.firstIndex(of: $0.id) }.max() ?? 0
        }
    }
    var body: some View {
        VStack(spacing: 4) {
            if !humans.isEmpty {
                ConditionSelector(
                    label: "要求モデル",
                    labels: humans.map { $0.name.replacingOccurrences(of: "Human ", with: "") },
                    value: Binding(
                        get: {
                            BrainConditionRange.indices(brain.conditions.answerer_ids, in: humans.map(\.id))
                        },
                        set: { range in
                            brain.conditions = BrainConditionRange.clamp(
                                brain.conditions, answerers: Array(humans[range]))
                        }), lowerMaximum: allowedMaximum, upperMaximum: allowedMaximum,
                    hint: "Lite、Standard、Proの順で、期待される生成品質が上昇します。回答によって得られる報酬も大きくなります。",
                    footer: brain.state?.rank_name == "Human Lite"
                        ? "Standard、Proを選択するには、ランクを上げる必要があります。"
                        : (brain.state?.rank_name == "Human Standard" ? "Proを選択するには、ランクを上げる必要があります。" : nil))
                ConditionSelector(
                    label: "思考の深さ", labels: BrainConditionRange.efforts.map(effortName),
                    value: Binding(
                        get: {
                            BrainConditionRange.indices(
                                brain.conditions.reasoning_efforts, in: BrainConditionRange.efforts)
                        },
                        set: {
                            brain.conditions.reasoning_efforts = Array(BrainConditionRange.efforts[$0])
                        }), lowerMaximum: maxima.min() ?? 0, upperMaximum: maxima.max() ?? 0,
                    hint: "思考が深いほど、期待される生成品質が上昇します。回答によって得られる報酬も大きくなります。",
                    footer: timingDescription)
            }
        }.disabled(brain.busy)
    }
    private var allowedMaximum: Int {
        humans.indices.filter { brain.state?.available_answerer_ids.contains(humans[$0].id) == true }.max()
            ?? 0
    }
    private var timingDescription: String {
        BrainConditionRange.efforts.compactMap { id in
            guard
                let seconds = humans.flatMap(\.reasoning_efforts).first(where: { $0.id == id })?
                    .execution_time_limit_seconds
            else { return nil }
            return effortName(id) + ": " + (seconds >= 3600 ? "\(seconds / 3600)時間" : "\(seconds / 60)分")
        }.joined(separator: "\n")
    }
}
private struct ConditionSelector: View {
    let label: String
    let labels: [String]
    @Binding var value: ClosedRange<Int>
    let lowerMaximum: Int
    let upperMaximum: Int
    let hint: String
    let footer: String?
    @State private var open = false
    var body: some View {
        Button {
            open = true
        } label: {
            HStack(spacing: 8) {
                Text(label).foregroundStyle(.secondary)
                Spacer()
                Text(
                    labels[value.lowerBound]
                        + (value.lowerBound == value.upperBound ? "" : "〜" + labels[value.upperBound])
                ).fontWeight(.medium)
                Image(systemName: "chevron.down").font(.caption2)
            }.font(.subheadline).frame(minHeight: 44).padding(.horizontal, 8)
        }
        .buttonStyle(.plain)
        .popover(isPresented: $open) {
            VStack(alignment: .leading, spacing: 16) {
                Text(label).font(.headline)
                DiscreteRangeSlider(
                    labels: labels, value: $value, lowerMaximum: lowerMaximum, upperMaximum: upperMaximum)
                Text(hint).font(.caption).foregroundStyle(.secondary)
                if let footer {
                    Divider()
                    Text(footer).font(.caption).foregroundStyle(.secondary)
                }
            }.padding(20).frame(width: 290).presentationCompactAdaptation(.popover)
        }
    }
}
private struct DiscreteRangeSlider: View {
    let labels: [String]
    @Binding var value: ClosedRange<Int>
    let lowerMaximum: Int
    let upperMaximum: Int
    var body: some View {
        VStack(spacing: 10) {
            GeometryReader { geometry in
                let width = max(1, geometry.size.width - 28)
                let denominator = CGFloat(max(1, labels.count - 1))
                let low = CGFloat(value.lowerBound) / denominator * width
                let high = CGFloat(value.upperBound) / denominator * width
                ZStack(alignment: .leading) {
                    Capsule().fill(SodAIStyle.border).frame(height: 4)
                    Capsule().fill(SodAIStyle.ink).frame(width: max(4, high - low), height: 4).offset(
                        x: low + 14)
                    thumb(lower: true, width: width, count: denominator).offset(
                        x: low - (value.lowerBound == value.upperBound ? 6 : 0))
                    thumb(lower: false, width: width, count: denominator).offset(
                        x: high + (value.lowerBound == value.upperBound ? 6 : 0))
                }.frame(height: 44).coordinateSpace(name: "range")
            }.frame(height: 44)
            HStack {
                ForEach(labels.indices, id: \.self) { index in
                    if index > 0 { Spacer(minLength: 2) }
                    Text(labels[index]).font(.caption2).foregroundStyle(
                        index <= upperMaximum ? SodAIStyle.ink : .secondary)
                }
            }
        }
    }
    private func thumb(lower: Bool, width: CGFloat, count: CGFloat) -> some View {
        Circle().fill(SodAIStyle.surface).overlay { Circle().strokeBorder(SodAIStyle.ink, lineWidth: 2) }
            .frame(width: 28, height: 28).contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0, coordinateSpace: .named("range")).onChanged { gesture in
                    let index = Int(((gesture.location.x - 14) / width * count).rounded())
                    update(index, lower: lower)
                }
            )
            .accessibilityElement().accessibilityLabel(lower ? "下限" : "上限")
            .accessibilityValue(labels[lower ? value.lowerBound : value.upperBound])
            .accessibilityAdjustableAction { direction in
                update(
                    (lower ? value.lowerBound : value.upperBound) + (direction == .increment ? 1 : -1),
                    lower: lower)
            }
    }
    private func update(_ index: Int, lower: Bool) {
        if lower {
            value = min(max(0, index), min(lowerMaximum, value.upperBound))...value.upperBound
        } else {
            value = value.lowerBound...max(value.lowerBound, min(index, upperMaximum))
        }
    }
}
