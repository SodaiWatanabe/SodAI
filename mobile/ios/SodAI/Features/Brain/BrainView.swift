import SwiftUI

struct BrainView: View {
    let openAccount: () -> Void
    @Environment(BrainStore.self) private var brain
    @Environment(PlatformStore.self) private var platform
    @Environment(AuthStore.self) private var auth
    @State private var decline = false
    @FocusState private var editing: Bool

    var body: some View {
        Group {
            if brain.needsValidation {
                ProgressView().accessibilityLabel("依頼を確認しています")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let assignment = brain.assignment {
                assignmentView(assignment)
            } else if brain.detailLoading {
                ProgressView().accessibilityLabel("回答履歴を読み込んでいます")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let detail = brain.detail {
                historyView(detail)
            } else {
                lobby
            }
        }
        .background(SodAIStyle.canvas)
        .alert("回答を辞退しますか？", isPresented: $decline) {
            Button("辞退する", role: .destructive) { Task { await brain.release() } }
            Button("キャンセル", role: .cancel) {}
        } message: {
            Text("入力中の回答は破棄されます。ペナルティが課される場合があります。")
        }
    }
    private var lobby: some View {
        ZStack {
            BrainBackground()
            VStack(spacing: 16) {
                if auth.user == nil {
                    primaryButton("ログイン", action: openAccount)
                } else if brain.state == nil {
                    if brain.loading { ProgressView().accessibilityLabel("読み込んでいます") }
                } else if brain.state?.status == "waiting" {
                    BrainWaitingGuide()
                    Button("待機をやめる") { Task { await brain.toggleReadiness() } }
                        .buttonStyle(.glass).disabled(brain.busy)
                } else {
                    VStack(spacing: 12) {
                        BrainConditionsView()
                        primaryButton("思考をはじめる") { Task { await brain.toggleReadiness() } }
                            .disabled(brain.busy)
                    }
                    .padding(16).glassEffect(.regular, in: RoundedRectangle(cornerRadius: 20))
                }
            }.multilineTextAlignment(.center).padding(24).frame(maxWidth: 440)
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    private func primaryButton(_ text: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text).font(.subheadline.weight(.medium)).padding(.horizontal, 22).frame(minHeight: 44)
                .foregroundStyle(SodAIStyle.canvas).background(SodAIStyle.ink, in: Capsule())
        }.buttonStyle(.plain)
    }
    private func assignmentView(_ assignment: BrainAssignment) -> some View {
        VStack(spacing: 0) {
            HStack {
                Text("\(Text("You are ").foregroundStyle(.secondary))\(assignment.answerer_name)")
                Spacer()
                TimelineView(.periodic(from: .now, by: 1)) { timeline in
                    let remaining = max(0, Int(ceil(assignment.deadline.timeIntervalSince(timeline.date))))
                    Text(String(format: "%d:%02d", remaining / 60, remaining % 60))
                        .monospacedDigit().accessibilityLabel("残り\(remaining)秒")
                }
            }.font(.subheadline).padding(.horizontal, 20).padding(.vertical, 12)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    context(assignment.context)
                    TextField(
                        "回答を書く", text: Binding(get: { brain.draft }, set: { brain.editDraft($0) }),
                        axis: .vertical
                    )
                    .lineLimit(8...30).font(.system(size: 16)).lineSpacing(8)
                    .focused($editing).disabled(brain.deadlineExpired)
                    .accessibilityLabel("回答").accessibilityIdentifier("brainAnswerInput")
                }.padding(20)
            }.scrollDismissesKeyboard(.interactively)
        }
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 8) {
                TimelineView(.periodic(from: .now, by: 1)) { timeline in
                    let expired = assignment.deadline <= timeline.date
                    HStack {
                        Spacer()
                        Button(assignment.canSkip(at: timeline.date) ? "スキップ" : "辞退する") {
                            if assignment.canSkip() { Task { await brain.release() } } else { decline = true }
                        }.foregroundStyle(assignment.canSkip(at: timeline.date) ? SodAIStyle.ink : .red)
                            .disabled(brain.busy || expired)
                        primaryButton("送信") {
                            editing = false
                            Task { if await brain.answer() { await platform.refreshCredits() } }
                        }.disabled(
                            brain.busy || expired
                                || brain.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
                .padding(8).background(SodAIStyle.surface, in: Capsule())
                .overlay { Capsule().strokeBorder(SodAIStyle.border, lineWidth: 0.5) }
            }.padding(.horizontal, 20).padding(.bottom, 8).background(SodAIStyle.canvas)
        }
    }
    private func historyView(_ detail: BrainAnswerDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                HStack {
                    Text("\(Text("You were ").foregroundStyle(.secondary))\(detail.answerer_name)")
                    Spacer()
                    Button("戻る") { brain.closeAnswer() }
                }.font(.subheadline)
                context(detail.context)
                ConversationText(content: detail.answer, human: false, perspective: .brain)
            }.padding(20)
        }
    }
    private func context(_ entries: [BrainContextEntry]) -> some View {
        ForEach(Array(entries.enumerated()), id: \.offset) { _, entry in
            ConversationText(content: entry.content, human: entry.author_kind == "human", perspective: .brain)
        }
    }
}

private struct BrainWaitingGuide: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let guides = [
        ("あなたはデータセンターの中にいます。", "ユーザーのクエリに、大規模言語モデルとして返答しましょう。"),
        ("より速く、より正確に。", "ユーザーは高速かつ高精度の回答を望んでいます。"),
        ("文脈を読み解く。", "会話の流れとユーザーの意図を踏まえて回答しましょう。"),
        ("結論から、明快に。", "最も重要な答えを先に示し、必要な理由を簡潔に続けましょう。"),
    ]
    var body: some View {
        TimelineView(.periodic(from: .now, by: 7)) { timeline in
            let index = reduceMotion ? 0 : Int(timeline.date.timeIntervalSince1970 / 7) % guides.count
            VStack(spacing: 10) {
                Text(guides[index].0).font(.title3.weight(.medium))
                Text(guides[index].1).font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
            }.frame(minHeight: 120)
        }
    }
}
