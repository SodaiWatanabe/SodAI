import AuthenticationServices
import SwiftUI

struct AccountView: View {
    @Environment(AuthStore.self) private var auth
    @Environment(PlatformStore.self) private var platform
    @Environment(\.webAuthenticationSession) private var webAuthentication

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let user = auth.user {
                    VStack(spacing: 8) {
                        Text(user.name).font(.title2.weight(.semibold))
                        Text(user.email).font(.subheadline).foregroundStyle(.secondary)
                            .accessibilityIdentifier("accountEmail")
                    }
                    if let credits = platform.credits {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("クレジット").font(.headline)
                            LabeledContent("残高", value: creditText(credits.available, scale: credits.scale))
                            if credits.reserved > 0 {
                                LabeledContent(
                                    "予約中", value: creditText(credits.reserved, scale: credits.scale))
                            }
                            if let allowance = credits.free_allowance {
                                let ratio = Double(allowance.remaining) / Double(max(1, allowance.limit))
                                LabeledContent("無料クレジット", value: "残り\(Int((ratio * 100).rounded()))%")
                                ProgressView(value: max(0, min(1, ratio)))
                                if let reset = PlatformDate.parse(allowance.expires_at) {
                                    Text("次回更新: " + reset.formatted(date: .abbreviated, time: .omitted)).font(
                                        .caption
                                    ).foregroundStyle(.secondary)
                                }
                            }
                        }.font(.subheadline).padding().background(
                            SodAIStyle.secondary, in: RoundedRectangle(cornerRadius: 16))
                    }
                    Button("ログアウト", role: .destructive) {
                        Task { await auth.signOut() }
                    }.accessibilityIdentifier("signOut")
                } else {
                    VStack(spacing: 10) {
                        Text("ログインまたは新規登録")
                            .font(.system(size: 24, weight: .semibold)).tracking(-0.8)
                        Text("ログインして、チャットを保存したり、高度なモデルにアクセスしたりしましょう。")
                            .font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
                            .multilineTextAlignment(.center)
                    }
                    Button {
                        Task {
                            await auth.signIn { url in
                                try await webAuthentication.authenticate(
                                    using: url, callback: .customScheme(OAuthAttempt.callbackScheme),
                                    preferredBrowserSession: .ephemeral, additionalHeaderFields: [:])
                            }
                        }
                    } label: {
                        HStack(spacing: 10) {
                            if auth.isSigningIn {
                                ProgressView().frame(width: 18, height: 18)
                            } else {
                                Image("GoogleMark")
                                    .renderingMode(.original)
                                    .resizable().scaledToFit()
                                    .frame(width: 18, height: 18)
                                    .accessibilityHidden(true)
                            }
                            Text("Googleで続行").font(.subheadline.weight(.medium))
                        }
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(SodAIStyle.surface, in: Capsule())
                        .overlay { Capsule().strokeBorder(SodAIStyle.border, lineWidth: 0.5) }
                    }
                    .buttonStyle(.plain)
                    .disabled(auth.isSigningIn || !auth.googleAvailable)
                    .opacity(auth.isSigningIn || !auth.googleAvailable ? 0.5 : 1)
                    .accessibilityIdentifier("googleSignIn")
                }
            }
            .padding(.horizontal, 28).padding(.top, 36)
        }
        .background(SodAIStyle.canvas)
        .navigationTitle(auth.user == nil ? "" : "アカウント")
        .navigationBarTitleDisplayMode(.inline)
        .task { await platform.refreshCredits() }
        .refreshable {
            await auth.prepare()
            await platform.refreshCredits()
        }
        .overlay { if auth.status == .restoring { ProgressView() } }
    }
}
