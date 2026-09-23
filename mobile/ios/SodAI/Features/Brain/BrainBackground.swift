import SwiftUI

/// Uses the same background assets and quiet central region as Web Brain.
struct BrainBackground: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scene
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Image(scheme == .dark ? "BrainNebula" : "BrainBloom")
                    .resizable().scaledToFill().frame(
                        width: geometry.size.width, height: geometry.size.height
                    )
                    .opacity(scheme == .dark ? 0.65 : 0.75).clipped()
                if scheme == .dark {
                    TimelineView(
                        .animation(minimumInterval: 1 / 30, paused: reduceMotion || scene != .active)
                    ) { timeline in
                        Canvas { context, size in
                            let elapsed = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate
                            let count = min(220, max(96, Int((size.width * size.height / 5500).rounded())))
                            for index in 0..<count {
                                let x = fraction(index * 731 + 13)
                                let y = fraction(index * 397 + 53)
                                if pow((x - 0.5) / 0.18, 2) + pow((y - 0.5) / 0.13, 2) < 1, index % 5 != 0 {
                                    continue
                                }
                                let depth = fraction(index * 173 + 7)
                                let radius = 0.38 + depth * 0.78
                                let phase = elapsed * (0.22 + depth * 0.24) + Double(index)
                                let alpha = (0.1 + depth * 0.34) * (1 + sin(phase) * 0.08)
                                let px = (x * size.width + elapsed * (depth - 0.5) * 0.4).truncatingRemainder(
                                    dividingBy: size.width)
                                let py = (y * size.height + elapsed * (depth - 0.5) * 0.2)
                                    .truncatingRemainder(dividingBy: size.height)
                                context.fill(
                                    Path(
                                        ellipseIn: CGRect(
                                            x: px < 0 ? px + size.width : px,
                                            y: py < 0 ? py + size.height : py, width: radius * 2,
                                            height: radius * 2)), with: .color(.white.opacity(alpha)))
                            }
                        }
                    }
                }
            }
        }.allowsHitTesting(false).accessibilityHidden(true)
    }
    private func fraction(_ value: Int) -> Double { Double((value * 1_103_515_245 + 12345) % 65536) / 65536 }
}
