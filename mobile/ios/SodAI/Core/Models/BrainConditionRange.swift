import Foundation

enum BrainConditionRange {
    static let efforts = ["low", "medium", "high", "xhigh"]
    static func indices(_ selected: [String], in options: [String]) -> ClosedRange<Int> {
        let indices = selected.compactMap { options.firstIndex(of: $0) }
        return (indices.min() ?? 0)...(indices.max() ?? 0)
    }
    static func clamp(_ conditions: BrainConditions, answerers: [Answerer]) -> BrainConditions {
        guard !answerers.isEmpty else { return .initial }
        let maxima = answerers.map { answerer in
            answerer.reasoning_efforts.compactMap { efforts.firstIndex(of: $0.id) }.max() ?? 0
        }
        let selected = indices(conditions.reasoning_efforts, in: efforts)
        let low = min(selected.lowerBound, maxima.min() ?? 0)
        let high = max(low, min(selected.upperBound, maxima.max() ?? 0))
        return .init(answerer_ids: answerers.map(\.id), reasoning_efforts: Array(efforts[low...high]))
    }
}
