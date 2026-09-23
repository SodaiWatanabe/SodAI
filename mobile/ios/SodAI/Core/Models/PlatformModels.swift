import Foundation

// The Web and native clients share the /api/v1 contracts; no local conversation database.
struct ItemPage<Item: Decodable & Sendable>: Decodable, Sendable { let items: [Item] }
struct Answerer: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let description: String
    let kind: String
    let is_default: Bool
    let is_legacy: Bool
    let pricing: Pricing
    let reasoning_efforts: [EffortOption]
    let default_reasoning_effort: String
}
struct Pricing: Decodable, Sendable {
    let kind: String
    let scale: Int
    let maximum_charge: Int
}
struct EffortOption: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let execution_time_limit_seconds: Int?
    let customer_charge: Int
    let performer_reward: Int
}
struct ThreadSummary: Decodable, Identifiable, Sendable {
    let id: String
    var title: String
    var answerer: String
    var revision: Int
    var last_activity_at: String
}
struct ChatActor: Decodable, Sendable {
    let id: String
    let kind: String
    let name: String
}
struct ChatEntry: Decodable, Identifiable, Sendable {
    let id: String
    let author: ChatActor
    let content: String
    let ordinal: Int
    let answerer: String?
    let response_status: String?
    let execution_id: String?
    var evaluation: String?
}
struct Execution: Decodable, Sendable {
    let id: String
    var result_entry_id: String?
    var status: String
    var partial_output: String
    var resolved_model: String?
    var generation_phase: String?
    var error_code: String?
    var evaluation: String?
}
struct ResponseRequest: Decodable, Sendable {
    let id: String
    let requested_answerer: String
    let reasoning_effort: String
    let target_actor: ChatActor
    var status: String
    var execution: Execution
    var isActive: Bool { status == "queued" || status == "running" }
}
struct ChatThread: Decodable, Identifiable, Sendable {
    let id: String
    var title: String
    var answerer: String
    var revision: Int
    var last_activity_at: String
    var entries: [ChatEntry]
    var latest_response: ResponseRequest?
    var summary: ThreadSummary {
        .init(
            id: id, title: title, answerer: answerer, revision: revision, last_activity_at: last_activity_at)
    }
    var displayEntries: [ChatEntry] {
        guard let response = latest_response else { return entries }
        let execution = response.execution
        if let result = execution.result_entry_id, entries.contains(where: { $0.id == result }) {
            return entries
        }
        return entries + [
            .init(
                id: "execution:" + execution.id, author: response.target_actor,
                content: execution.partial_output, ordinal: (entries.last?.ordinal ?? -1) + 1,
                answerer: response.requested_answerer, response_status: response.status,
                execution_id: execution.id, evaluation: execution.evaluation)
        ]
    }
}
struct ResponseCreation: Decodable, Sendable {
    let thread: ChatThread
    let response: ResponseRequest
}
struct ThreadSearchHit: Decodable, Identifiable, Sendable {
    let thread: ThreadSummary
    let snippet: String
    let entry_id: String?
    var id: String { thread.id }
}
struct ThreadSearchPage: Decodable, Sendable {
    let items: [ThreadSearchHit]
    let has_more: Bool
}
struct RealtimeTicket: Decodable, Sendable {
    let ticket: String
    let cursor: Int
}
struct RealtimeEvent: Decodable, Sendable {
    let type: String
    let sequence: Int?
    let cursor: Int?
    let thread_id: String?
    let thread_revision: Int?
    let response_request_id: String?
    let execution_id: String?
    let data: Payload?
    struct Payload: Decodable, Sendable {
        let content: String?
        let phase: String?
        let resolved_model: String?
        let result_entry_id: String?
        let error_code: String?
        let claim_id: String?
        let reason: String?
    }
}
struct BrainConditions: Codable, Equatable, Sendable {
    var answerer_ids: [String]
    var reasoning_efforts: [String]
    static let initial = Self(answerer_ids: ["human-lite"], reasoning_efforts: ["low"])
}
struct BrainContextEntry: Decodable, Sendable {
    let author_kind: String
    let content: String
}
struct BrainAssignment: Decodable, Sendable {
    let claim_id: String
    let answerer_name: String
    let reasoning_effort: String
    let skip_allowed_until: String
    let deadline_at: String
    let draft_content: String
    let draft_revision: Int
    let context: [BrainContextEntry]
    var deadline: Date { PlatformDate.parse(deadline_at) ?? .distantPast }
    func canSkip(at date: Date = Date()) -> Bool {
        date < (PlatformDate.parse(skip_allowed_until) ?? .distantPast)
    }
}
struct BrainState: Decodable, Sendable {
    var status: String
    let rank_name: String
    var assignment: BrainAssignment?
    let answer_conditions: BrainConditions
    let available_answerer_ids: [String]
}
struct BrainAnswerSummary: Decodable, Identifiable, Sendable {
    let execution_id: String
    let answerer_name: String
    let reasoning_effort: String
    let prompt_preview: String
    let answered_at: String
    var id: String { execution_id }
}
struct BrainAnswerPage: Decodable, Sendable {
    let items: [BrainAnswerSummary]
    let next_cursor: String?
}
struct BrainAnswerDetail: Decodable, Sendable {
    let execution_id: String
    let answerer_name: String
    let reasoning_effort: String
    let answered_at: String
    let context: [BrainContextEntry]
    let answer: String
}
struct DraftReceipt: Decodable, Sendable { let revision: Int }
struct CreditBalance: Decodable, Sendable {
    let scale: Int
    let available: Int
    let reserved: Int
    let free_allowance: Allowance?
    struct Allowance: Decodable, Sendable {
        let limit: Int
        let remaining: Int
        let expires_at: String
    }
}
enum PlatformDate {
    static func parse(_ value: String) -> Date? {
        // FastAPI emits fractional seconds; both variants occur in the same API.
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }
}
func effortName(_ id: String) -> String {
    ["none": "なし", "low": "軽い", "medium": "中程度", "high": "深い", "xhigh": "非常に深い"][id] ?? id
}
func creditText(_ units: Int, scale: Int) -> String {
    (Double(units) / Double(max(1, scale))).formatted(.number.precision(.fractionLength(0...6)))
}
