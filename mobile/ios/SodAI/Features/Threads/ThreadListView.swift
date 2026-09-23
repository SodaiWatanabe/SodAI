import SwiftUI

struct ThreadListView: View {
    @Binding var product: SodAIProduct
    let isOpen: Bool
    let close: () -> Void
    let openAccount: () -> Void
    @Environment(ConversationStore.self) private var chat
    @Environment(BrainStore.self) private var brain
    @Environment(AuthStore.self) private var auth
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var search = ""
    @State private var searching = false
    @FocusState private var searchFocused: Bool
    @State private var renaming: ThreadSummary?
    @State private var title = ""
    private var isSearchLoading: Bool {
        product == .chat && chat.searching && !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if searching, product == .chat { searchField }
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        Text(product == .chat ? (search.isEmpty ? "会話" : "検索結果") : "回答履歴")
                            .font(.system(size: 16, weight: .semibold)).foregroundStyle(.secondary)
                            .padding(.horizontal, 12).padding(.top, 16).padding(.bottom, 12)
                            .accessibilityAddTraits(.isHeader)
                        if product == .chat { chatHistory } else { brainHistory }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 8).padding(.bottom, 100)
                }
                .scrollDismissesKeyboard(.interactively)
                .refreshable {
                    if product == .chat { await chat.refreshList() } else { await brain.refreshHistory() }
                }
                .overlay {
                    if isSearchLoading {
                        ProgressView()
                            .controlSize(.regular)
                            .tint(.secondary)
                            .accessibilityLabel("会話を検索しています")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .padding(.bottom, SodAIStyle.bottomControlHeight)
                            .allowsHitTesting(false)
                    }
                }
                .ignoresSafeArea(.container, edges: .bottom)
            }
            .overlay(alignment: .bottom) { footer }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { productMenu }
                    .sharedBackgroundVisibility(.hidden)
                if product == .chat {
                    ToolbarItem(placement: .topBarTrailing) { searchToggle }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
        }
        .foregroundStyle(SodAIStyle.ink)
        .task(id: search) { await chat.search(search) }
        .onChange(of: isOpen) { _, open in
            if !open { resetSearch() }
        }
        .onChange(of: product) { resetSearch() }
        .alert("名前を変更", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
            TextField("会話の名前", text: $title)
            Button("キャンセル", role: .cancel) { renaming = nil }
            Button("保存") {
                if let thread = renaming {
                    Task {
                        await chat.rename(thread.id, title: title)
                        if !search.isEmpty { await chat.search(search) }
                    }
                }
                renaming = nil
            }.disabled(
                title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    || title.unicodeScalars.count > 120)
        }
    }

    private var productMenu: some View {
        Menu {
            Button {
                product = .chat
            } label: {
                Text("Chat")
                Text("モデルと会話する。")
            }.accessibilityIdentifier("switchChat")
            Button {
                product = .brain
            } label: {
                Text("Brain")
                Text("思考を引き受ける。")
            }.accessibilityIdentifier("switchBrain")
        } label: {
            HStack(spacing: 5) {
                // Keep the changing name outside interpolated Text: the toolbar menu's
                // dismissal animation otherwise hides just that run during a switch.
                HStack(spacing: 4) {
                    Text("SodAI")
                    Text(product.rawValue).foregroundStyle(.secondary)
                        .contentTransition(.identity)
                }
                .tracking(-0.6).lineLimit(1)
                Image(systemName: "chevron.down").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            }
            .transaction {
                $0.animation = nil
                $0.disablesAnimations = true
            }
            .fixedSize(horizontal: true, vertical: false)
            .contentShape(Rectangle())
        }
        .font(.system(size: 22, weight: .semibold))
        .buttonStyle(.plain)
        .padding(.leading, -8)
        .disabled(brain.assigned)
        .accessibilityLabel("SodAI " + product.rawValue + "、機能を切り替える")
        .accessibilityIdentifier("productSwitcher")
    }

    private var searchToggle: some View {
        Button {
            withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.18)) { searching.toggle() }
            if !searching { search = "" }
            searchFocused = searching
        } label: {
            Image(systemName: searching ? "xmark" : "magnifyingglass")
                .font(.system(size: 18, weight: .medium))
        }
        .accessibilityLabel(searching ? "検索を閉じる" : "会話を検索")
        .accessibilityIdentifier("toggleThreadSearch")
    }

    private var searchField: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
            TextField("会話を検索", text: $search)
                .font(.system(size: 16)).focused($searchFocused)
                .submitLabel(.search).autocorrectionDisabled()
                .onSubmit { searchFocused = false }
                .accessibilityIdentifier("threadSearch")
        }
        .padding(12).background(SodAIStyle.secondary, in: RoundedRectangle(cornerRadius: 14))
        .padding(.horizontal, 20).padding(.bottom, 8)
    }

    private var footer: some View {
        HStack(spacing: 12) {
            Button {
                if product == .chat { chat.newConversation() } else { brain.closeAnswer() }
                close()
            } label: {
                Label(
                    product == .chat ? "新しい会話" : "思考する",
                    systemImage: product == .chat ? "square.and.pencil" : "brain"
                )
                .font(.system(size: 16, weight: .semibold)).padding(.vertical, 6).padding(.horizontal, 4)
            }
            .buttonStyle(.glassProminent).tint(SodAIStyle.ink).foregroundStyle(SodAIStyle.canvas)
            .disabled(brain.assigned)
            .accessibilityIdentifier(product == .chat ? "newConversation" : "brainHome")
            Spacer(minLength: 0)
            Button(action: openAccount) {
                Image(systemName: "person.crop.circle").font(.system(size: 22))
                    .frame(width: 30, height: 34)
            }
            .buttonStyle(.glass).buttonBorderShape(.circle)
            .accessibilityLabel(auth.user.map { $0.name + "、アカウント" } ?? "ログイン")
            .accessibilityIdentifier("sidebarAccount")
        }
        .frame(minHeight: SodAIStyle.bottomControlHeight)
        .padding(.horizontal, 20)
    }

    @ViewBuilder private var chatHistory: some View {
        if search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            ForEach(chat.threads) { thread in row(thread) }
            if chat.threads.isEmpty { hint("会話はまだありません。") }
        } else if !chat.searching, let page = chat.searchPage {
            ForEach(page.items) { hit in row(hit.thread, entryID: hit.entry_id) }
            if page.items.isEmpty { hint("会話が見つかりませんでした。") }
            if page.has_more { hint("検索語を追加して絞り込んでください。") }
        }
    }

    private func row(_ thread: ThreadSummary, entryID: String? = nil) -> some View {
        Button {
            close()
            Task { await chat.select(thread.id, entryID: entryID) }
        } label: {
            Text(thread.title).font(.system(size: 16)).lineLimit(1).truncationMode(.tail)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 12).padding(.vertical, 12)
                .background(
                    chat.selectedID == thread.id ? SodAIStyle.secondary : .clear,
                    in: RoundedRectangle(cornerRadius: 12)
                )
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("threadRow:" + thread.id)
        .accessibilityAddTraits(chat.selectedID == thread.id ? .isSelected : [])
        .disabled(brain.assigned)
        .contextMenu {
            Button("名前を変更", systemImage: "pencil") {
                title = thread.title
                renaming = thread
            }
            Button("アーカイブ", systemImage: "archivebox") {
                Task {
                    await chat.archive(thread.id)
                    if !search.isEmpty { await chat.search(search) }
                }
            }
        }
    }

    @ViewBuilder private var brainHistory: some View {
        ForEach(brain.history) { item in
            Button {
                close()
                Task { await brain.openAnswer(item.id) }
            } label: {
                Text(item.prompt_preview).font(.system(size: 16)).lineLimit(1).truncationMode(.tail)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12).padding(.vertical, 12)
                    .background(
                        brain.detail?.execution_id == item.id ? SodAIStyle.secondary : .clear,
                        in: RoundedRectangle(cornerRadius: 12)
                    )
                    .contentShape(Rectangle())
            }.buttonStyle(.plain).disabled(brain.assigned)
        }
        if brain.historyLoading {
            ProgressView().accessibilityLabel("回答履歴を読み込んでいます").padding(12)
        } else if brain.history.isEmpty {
            hint("回答履歴はまだありません。")
        }
        if brain.nextCursor != nil {
            Button("さらに読み込む") { Task { await brain.refreshHistory(more: true) } }
                .font(.system(size: 16)).padding(12).disabled(brain.historyLoading)
        }
    }

    private func hint(_ message: String) -> some View {
        Text(message).font(.system(size: 16)).foregroundStyle(.secondary).padding(12)
    }
    private func resetSearch() {
        searchFocused = false
        searching = false
        search = ""
    }
}
