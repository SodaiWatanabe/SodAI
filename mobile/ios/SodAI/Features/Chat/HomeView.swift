import SwiftUI

enum SodAIProduct: String, CaseIterable {
    case chat = "Chat"
    case brain = "Brain"
}

struct HomeView: View {
    @Environment(AuthStore.self) private var auth
    @Environment(PlatformStore.self) private var platform
    @Environment(ConversationStore.self) private var chat
    @Environment(BrainStore.self) private var brain
    @State private var product = SodAIProduct.chat
    @State private var sidebar = SidebarState()
    @State private var accountOpen = false
    @State private var privacy = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var sidebarOpen: Bool { sidebar.isOpen }
    var body: some View {
        SidebarContainer(state: sidebar, gesturesEnabled: !accountOpen) {
            ThreadListView(
                product: $product, isOpen: sidebarOpen, close: { setSidebar(false) },
                openAccount: {
                    setSidebar(false)
                    accountOpen = true
                })
        } content: {
            mainContent
        }
        .sheet(isPresented: $accountOpen) {
            NavigationStack {
                AccountView().toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("閉じる") { accountOpen = false } }
                }
            }
        }
        .alert(chat.current == nil ? "Humanへの送信" : "会話が共有されます", isPresented: $privacy) {
            Button("確認しました", role: .cancel) {}
        } message: {
            Text(
                chat.current == nil
                    ? "プロンプトは第三者のユーザーに送信されます。個人情報と機密情報は含めないようにしてください。"
                    : "このスレッド内の全メッセージが第三者のユーザーに送信されます。個人情報と機密情報は含めないようにしてください。")
        }
        .task(id: product) { await platform.setBrainVisible(product == .brain) }
        .sensoryFeedback(.selection, trigger: product)
        .onChange(of: brain.assignment?.claim_id) { _, claim in
            if claim != nil {
                product = .brain
                accountOpen = false
                setSidebar(false)
                brain.closeAnswer()
            }
        }
    }
    private var mainContent: some View {
        NavigationStack {
            Group {
                if product == .chat { ChatView() } else { BrainView(openAccount: { accountOpen = true }) }
            }
            .accessibilityHidden(sidebarOpen)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("サイドバーを開く", systemImage: "equal") { setSidebar(true) }
                        .labelStyle(.iconOnly).accessibilityIdentifier("conversationMenu")
                        .accessibilityHidden(sidebarOpen)
                }
                if product == .chat {
                    ToolbarSpacer(.fixed, placement: .topBarLeading)
                    ToolbarItem(placement: .topBarLeading) { modelMenu }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
        }
    }
    private func setSidebar(_ open: Bool) {
        sidebar.setOpen(open, reduceMotion: reduceMotion)
    }
    private var currentModels: [Answerer] { chat.answerers.filter { $0.kind == "ai" && !$0.is_legacy } }
    private var humanModels: [Answerer] { chat.answerers.filter { $0.kind == "human" && !$0.is_legacy } }
    private var pastModels: [Answerer] { chat.answerers.filter { $0.kind == "ai" && $0.is_legacy } }
    private var modelMenu: some View {
        Menu {
            if auth.user == nil {
                Text("よりスマートな回答")
                Button("ログイン") { accountOpen = true }
            } else {
                ForEach(currentModels) { answerer in modelButton(answerer) }
                if !humanModels.isEmpty {
                    Divider()
                    Menu {
                        ForEach(humanModels) { answerer in modelButton(answerer) }
                    } label: {
                        Text("Human")
                        Text("人類の底力。")
                    }
                    .accessibilityIdentifier("humanModels")
                }
                if !pastModels.isEmpty {
                    Divider()
                    Menu("過去のAIモデル") {
                        ForEach(pastModels) { answerer in modelButton(answerer) }
                    }
                    .accessibilityIdentifier("pastModels")
                }
            }
        } label: {
            HStack(spacing: 5) {
                Text(chat.selectedAnswerer?.name ?? "SodAI").font(.subheadline.weight(.medium))
                Image(systemName: "chevron.down").font(.caption2)
            }
        }
        .menuOrder(.fixed)
        .accessibilityLabel("モデル: " + (chat.selectedAnswerer?.name ?? "読み込み中"))
        .accessibilityIdentifier("modelPicker")
        .accessibilityHidden(sidebarOpen)
        .disabled(chat.selectedAnswerer == nil || chat.busy || chat.responding)
    }
    private func modelButton(_ answerer: Answerer) -> some View {
        Button {
            if chat.selectedAnswerer?.kind == "ai", answerer.kind == "human" { privacy = true }
            chat.chooseAnswerer(answerer.id)
        } label: {
            if chat.answererID == answerer.id {
                Label(answerer.name, systemImage: "checkmark")
            } else {
                Text(answerer.name)
            }
            Text(answerer.description)
        }
        .accessibilityIdentifier("modelOption:" + answerer.id)
    }
}
