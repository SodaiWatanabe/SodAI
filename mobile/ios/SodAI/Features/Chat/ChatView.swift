import SwiftUI

struct ChatView: View {
    @Environment(ConversationStore.self) private var store
    @FocusState private var composing: Bool
    @State private var atBottom = true
    @State private var copied: String?
    @State private var composerHeight = SodAIStyle.bottomControlHeight
    @State private var keyboardVisible = false
    private var messages: [ChatEntry] { store.current?.displayEntries ?? [] }

    var body: some View {
        Group {
            if messages.isEmpty, store.selectedID == nil, !store.loading {
                Color.clear
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .contentShape(Rectangle())
                    .accessibilityIdentifier("newConversationCanvas")
            } else {
                conversation
            }
        }
        .background(SodAIStyle.canvas)
        .overlay(alignment: .bottom) {
            composer
                .padding(.bottom, composing && keyboardVisible ? 8 : 0)
                .onGeometryChange(for: CGFloat.self) {
                    $0.size.height
                } action: {
                    composerHeight = $0
                }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillShowNotification)) { _ in
            keyboardVisible = true
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            keyboardVisible = false
        }
        .onChange(of: store.selectedID) { composing = false }
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                if store.loading {
                    ProgressView()
                        .accessibilityLabel("会話を読み込んでいます")
                        .frame(maxWidth: .infinity).padding(.top, 80)
                } else {
                    VStack(alignment: .leading, spacing: 28) {
                        ForEach(messages) { message in
                            VStack(alignment: .leading, spacing: 8) {
                                ConversationText(
                                    content: message.content, human: message.author.kind == "human",
                                    perspective: .chat
                                )
                                .accessibilityIdentifier(
                                    message.author.kind == "human" ? "userMessage" : "assistantMessage")
                                if message.author.kind != "human" { responseFooter(message) }
                            }.id(message.id)
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }.padding(.horizontal, 20).padding(.vertical, 24)
                }
            }
            .accessibilityIdentifier("conversationScroll")
            .safeAreaPadding(.bottom, composerHeight)
            .scrollDismissesKeyboard(.interactively)
            .onScrollGeometryChange(for: Bool.self) { geometry in
                geometry.contentOffset.y + geometry.containerSize.height >= geometry.contentSize.height
                    + geometry.contentInsets.bottom - 32
            } action: { _, value in
                atBottom = value
            }
            .refreshable {
                await store.refreshCurrent()
                await store.refreshList()
            }
            .onChange(of: messages.count, initial: true) {
                guard !messages.isEmpty else { return }
                if let anchor = store.searchAnchor {
                    proxy.scrollTo(anchor, anchor: .center)
                    store.searchAnchor = nil
                } else {
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }
            .onChange(of: messages.last?.content) {
                if atBottom { proxy.scrollTo("bottom", anchor: .bottom) }
            }
        }
    }
    @ViewBuilder private func responseFooter(_ entry: ChatEntry) -> some View {
        let latest = store.current?.latest_response
        let isLatest = entry.execution_id == latest?.execution.id
        let isResponding = isLatest && latest?.isActive == true
        if !isResponding, entry.response_status != "failed" {
            completedResponseFooter(entry, isLatest: isLatest)
        }
    }
    @ViewBuilder private func completedResponseFooter(_ entry: ChatEntry, isLatest: Bool) -> some View {
        HStack(spacing: 4) {
            action(
                copied == entry.id ? "コピーしました" : "本文をコピー",
                icon: copied == entry.id ? "checkmark" : "doc.on.doc"
            ) {
                UIPasteboard.general.string = entry.content
                copied = entry.id
            }
            if entry.execution_id != nil, entry.response_status != "cancelled" {
                action("良い回答", icon: entry.evaluation == "positive" ? "hand.thumbsup.fill" : "hand.thumbsup")
                {
                    Task { await store.evaluate(entry, value: "positive") }
                }.disabled(store.busy)
                action(
                    "良くない回答",
                    icon: entry.evaluation == "negative" ? "hand.thumbsdown.fill" : "hand.thumbsdown"
                ) {
                    Task { await store.evaluate(entry, value: "negative") }
                }.disabled(store.busy)
            }
            Menu {
                Text("使用したモデル")
                Text(store.answerers.first(where: { $0.id == entry.answerer })?.name ?? entry.author.name)
            } label: {
                Image(systemName: "brain").frame(width: 40, height: 40)
            }
            .accessibilityLabel("使用したモデル")
            if isLatest {
                action("回答を再生成", icon: "arrow.clockwise") { Task { await store.regenerate() } }
                    .disabled(store.busy || store.responding)
            }
        }.font(.subheadline).foregroundStyle(.secondary).buttonStyle(.plain)
    }
    private func action(_ label: String, icon: String, perform: @escaping () -> Void) -> some View {
        Button(action: perform) { Image(systemName: icon).frame(width: 40, height: 40) }.accessibilityLabel(
            label)
    }
    private var composer: some View {
        // Changing layout preserves the editor's identity, focus, and selection.
        let layout =
            composing
            ? AnyLayout(VStackLayout(spacing: 0))
            : AnyLayout(HStackLayout(alignment: .bottom, spacing: 4))
        return layout {
            messageInput
                .padding(.leading, 22).padding(.trailing, composing ? 22 : 0)
                .padding(.top, 15).padding(.bottom, composing ? 2 : 15)
                .frame(minHeight: composing ? nil : SodAIStyle.bottomControlHeight)
            HStack(spacing: 4) {
                if composing, let answerer = store.selectedAnswerer, answerer.kind == "human" {
                    reasoningMenu(answerer).padding(.leading, 8)
                }
                if composing { Spacer(minLength: 0) }
                composerAction
            }.fixedSize(horizontal: !composing, vertical: false).layoutPriority(1)
        }
        .buttonStyle(.plain)
        .frame(minHeight: SodAIStyle.bottomControlHeight)
        .glassEffect(.regular, in: RoundedRectangle(cornerRadius: 28))
        .contentShape(RoundedRectangle(cornerRadius: 28))
        .onTapGesture { composing = true }
        .background {
            ComposerOutsideTapObserver(isEditing: composing) { composing = false }
                .allowsHitTesting(false)
                .accessibilityHidden(true)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("messageComposer")
        .padding(.horizontal, 20)
    }
    private var messageInput: some View {
        @Bindable var store = store
        return TextField("話しかけてください", text: $store.draft, axis: .vertical)
            .lineLimit(composing ? 1...6 : 1...1).font(.system(size: 16))
            .focused($composing).accessibilityLabel("SodAIへのメッセージ")
            .accessibilityIdentifier("messageInput")
    }
    private func reasoningMenu(_ answerer: Answerer) -> some View {
        @Bindable var store = store
        let name =
            answerer.reasoning_efforts.first(where: { $0.id == store.reasoningEffort })?.name
            ?? effortName(store.reasoningEffort)
        return Menu {
            Picker("思考の深さ", selection: $store.reasoningEffort) {
                ForEach(answerer.reasoning_efforts) { option in
                    Text(option.name).tag(option.id).accessibilityIdentifier("reasoningOption:" + option.id)
                }
            }
        } label: {
            HStack(spacing: 5) {
                Text(name).font(.system(size: 16, weight: .medium)).lineLimit(1)
                Image(systemName: "chevron.down").font(.caption2)
            }
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14).frame(minHeight: 44)
            .contentShape(Capsule())
        }
        .menuOrder(.fixed)
        .disabled(store.busy || store.responding)
        .accessibilityLabel("思考の深さ: " + name)
        .accessibilityIdentifier("reasoningPicker")
    }
    @ViewBuilder private var composerAction: some View {
        if store.responding {
            Button {
                Task { await store.cancel() }
            } label: {
                sendIcon("stop.fill")
            }
            .disabled(store.busy).accessibilityLabel("回答を停止").padding(8)
        } else {
            Button {
                composing = false
                Task { _ = await store.send() }
            } label: {
                if store.busy {
                    ProgressView().frame(width: 40, height: 40)
                } else {
                    sendIcon("arrow.up").opacity(store.canSend ? 1 : 0.25)
                }
            }
            .disabled(!store.canSend).accessibilityLabel("送信").accessibilityIdentifier("sendMessage").padding(
                8)
        }
    }
    private func sendIcon(_ icon: String) -> some View {
        Image(systemName: icon).font(.system(size: 18, weight: .semibold))
            .frame(width: 40, height: 40).foregroundStyle(SodAIStyle.canvas).background(
                SodAIStyle.ink, in: Circle())
    }
}

// Observe outside taps without consuming controls, text selection, or scrolling.
private struct ComposerOutsideTapObserver: UIViewRepresentable {
    let isEditing: Bool
    let dismiss: () -> Void

    func makeUIView(context: Context) -> ObserverView { ObserverView() }

    func updateUIView(_ view: ObserverView, context: Context) {
        view.tap.isEnabled = isEditing
        view.dismiss = dismiss
    }

    static func dismantleUIView(_ view: ObserverView, coordinator: ()) {
        view.tap.view?.removeGestureRecognizer(view.tap)
    }

    final class ObserverView: UIView, UIGestureRecognizerDelegate {
        var dismiss: (() -> Void)?
        lazy var tap: UITapGestureRecognizer = {
            let gesture = UITapGestureRecognizer(target: self, action: #selector(tappedOutside))
            gesture.cancelsTouchesInView = false
            gesture.delaysTouchesEnded = false
            gesture.delegate = self
            return gesture
        }()

        override func didMoveToWindow() {
            super.didMoveToWindow()
            tap.view?.removeGestureRecognizer(tap)
            window?.addGestureRecognizer(tap)
        }

        @objc private func tappedOutside() { dismiss?() }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool
        {
            guard let window, touch.view?.window === window,
                !bounds.contains(touch.location(in: self)),
                !window.keyboardLayoutGuide.layoutFrame.contains(touch.location(in: window))
            else { return false }
            var touchedView = touch.view
            while let view = touchedView {
                if view is UITextField { return false }
                if let text = view as? UITextView, text.isEditable { return false }
                touchedView = view.superview
            }
            return true
        }

        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
        ) -> Bool { true }
    }
}

struct ConversationText: View {
    let content: String
    let human: Bool
    let perspective: SodAIProduct
    var body: some View {
        HStack {
            if human && perspective == .chat { Spacer(minLength: 40) }
            Text(content).font(.system(size: 16)).lineSpacing(human ? 5 : 8).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, human ? 16 : 0).padding(.vertical, human ? 11 : 0)
                .background(human ? SodAIStyle.secondary : .clear, in: RoundedRectangle(cornerRadius: 22))
                .frame(maxWidth: human ? nil : .infinity, alignment: .leading)
            if human && perspective == .brain { Spacer(minLength: 40) }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
