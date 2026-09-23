import SwiftUI

@MainActor @Observable
final class SidebarState {
    private(set) var isOpen = false
    private(set) var translation: CGFloat?
    @ObservationIgnored private let feedback = UISelectionFeedbackGenerator()

    func drag(to translation: CGFloat) {
        if self.translation == nil {
            feedback.prepare()
        }
        self.translation = translation
    }

    func setOpen(_ open: Bool, reduceMotion: Bool) {
        if isOpen != open {
            if translation == nil { feedback.prepare() }
            feedback.selectionChanged()
        }
        withAnimation(reduceMotion ? .easeOut(duration: 0.15) : .spring(duration: 0.32, bounce: 0)) {
            isOpen = open
            translation = nil
        }
    }
}

struct SidebarContainer<Sidebar: View, Content: View>: View {
    let state: SidebarState
    var gesturesEnabled = true
    @ViewBuilder let sidebar: () -> Sidebar
    @ViewBuilder let content: () -> Content
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme
    @State private var topCornerRadius: CGFloat = 0
    @State private var bottomCornerRadius: CGFloat = 0
    private var isOpen: Bool { state.isOpen }
    private var mainPaneShape: UnevenRoundedRectangle {
        UnevenRoundedRectangle(
            topLeadingRadius: topCornerRadius, bottomLeadingRadius: bottomCornerRadius, style: .continuous)
    }
    private var mainPaneBorder: LinearGradient {
        let ink = colorScheme == .dark ? Color.white : Color.black
        return LinearGradient(
            colors: [ink.opacity(0.28), ink.opacity(0.13), ink.opacity(0.22)],
            startPoint: .topLeading, endPoint: .bottomLeading)
    }

    var body: some View {
        GeometryReader { geometry in
            let width = min(360, max(0, geometry.size.width - 64))
            let offset = min(width, max(0, (isOpen ? width : 0) + (state.translation ?? 0)))
            let progress = width > 0 ? offset / width : 0

            // Both panes share one translation, as adjacent parts of a wider canvas.
            HStack(spacing: 0) {
                sidebar()
                    .frame(width: width)
                    .frame(maxHeight: .infinity)
                    .background(SodAIStyle.canvas.ignoresSafeArea())
                    .allowsHitTesting(isOpen)
                    .accessibilityHidden(!isOpen)
                    .accessibilityAction(.escape) { settle(open: false) }

                content()
                    .frame(width: geometry.size.width)
                    .allowsHitTesting(!isOpen)
                    .accessibilityElement(children: isOpen ? .ignore : .contain)
                    .accessibilityHidden(isOpen)
                    .background(SodAIStyle.canvas.ignoresSafeArea())
                    .overlay {
                        (colorScheme == .dark ? Color.white : Color.black)
                            .opacity(0.08 * progress).ignoresSafeArea().allowsHitTesting(false)
                    }
            }
            .offset(x: offset - width)
            .frame(width: geometry.size.width, height: geometry.size.height, alignment: .leading)
            .mask(alignment: .leading) {
                ZStack(alignment: .leading) {
                    Rectangle().frame(width: offset)
                    // Resolve the screen's curvature before translating the main pane.
                    mainPaneShape
                        .offset(x: offset)
                }
                .ignoresSafeArea(.container)
            }
            .background(SodAIStyle.canvas.ignoresSafeArea())
            .overlay(alignment: .leading) {
                mainPaneShape.strokeBorder(mainPaneBorder, lineWidth: 1)
                    .ignoresSafeArea(.container)
                    .offset(x: offset)
                    .opacity(progress)
                    .allowsHitTesting(false)
                    .accessibilityHidden(true)
            }
            .overlay(alignment: .leading) {
                Button {
                    settle(open: false)
                } label: {
                    Color.clear.contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .frame(width: geometry.size.width - offset)
                .ignoresSafeArea()
                .offset(x: offset)
                .accessibilityLabel("サイドバーを閉じる")
                .accessibilityIdentifier("closeSidebar")
                .allowsHitTesting(isOpen)
                .accessibilityHidden(!isOpen)
            }
            .gesture(
                SidebarPanGesture(isOpen: isOpen, enabled: gesturesEnabled) { value in
                    if state.translation == nil { dismissKeyboard() }
                    state.drag(to: value)
                } ended: { value, velocity, cancelled in
                    let projected = (isOpen ? width : 0) + value + velocity * 0.18
                    settle(open: cancelled ? isOpen : projected > width * 0.5)
                })
        }
        .background {
            ScreenCornerReader { top, bottom in
                topCornerRadius = top
                bottomCornerRadius = bottom
            }
            .ignoresSafeArea(.container)
            .allowsHitTesting(false)
            .accessibilityHidden(true)
        }
        .onChange(of: isOpen) { _, opened in
            if opened { dismissKeyboard() }
        }
    }

    private func settle(open: Bool) {
        state.setOpen(open, reduceMotion: reduceMotion)
    }

    private func dismissKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }
}

// Resolve the device's corners before the panes move. Sharing these radii keeps
// the mask and its inset border identical throughout the horizontal gesture.
private struct ScreenCornerReader: UIViewRepresentable {
    let changed: (CGFloat, CGFloat) -> Void

    func makeUIView(context: Context) -> CornerView {
        let view = CornerView()
        view.cornerConfiguration = .corners(radius: .containerConcentric())
        view.isUserInteractionEnabled = false
        view.changed = changed
        return view
    }

    func updateUIView(_ view: CornerView, context: Context) { view.changed = changed }

    final class CornerView: UIView {
        var changed: ((CGFloat, CGFloat) -> Void)?
        private var lastRadii: CGSize?

        override func layoutSubviews() {
            super.layoutSubviews()
            guard window != nil, !bounds.isEmpty else { return }
            let radii = CGSize(
                width: effectiveRadius(corner: .topLeft), height: effectiveRadius(corner: .bottomLeft))
            guard radii != lastRadii else { return }
            lastRadii = radii
            DispatchQueue.main.async { [weak self] in self?.changed?(radii.width, radii.height) }
        }
    }
}

// Decide horizontal intent before recognizing so scrolling, text selection and
// controls keep their native gestures. Right swipes open from across the content.
private struct SidebarPanGesture: UIGestureRecognizerRepresentable {
    let isOpen: Bool
    let enabled: Bool
    let changed: (CGFloat) -> Void
    let ended: (CGFloat, CGFloat, Bool) -> Void

    func makeCoordinator(converter: CoordinateSpaceConverter) -> Coordinator { Coordinator() }

    func makeUIGestureRecognizer(context: Context) -> UIPanGestureRecognizer {
        let recognizer = UIPanGestureRecognizer()
        recognizer.maximumNumberOfTouches = 1
        recognizer.delegate = context.coordinator
        context.coordinator.isOpen = isOpen
        return recognizer
    }

    func updateUIGestureRecognizer(_ recognizer: UIPanGestureRecognizer, context: Context) {
        context.coordinator.isOpen = isOpen
        recognizer.isEnabled = enabled
    }

    func handleUIGestureRecognizerAction(_ recognizer: UIPanGestureRecognizer, context: Context) {
        let translation = recognizer.translation(in: recognizer.view).x
        switch recognizer.state {
        case .began, .changed: changed(translation)
        case .ended: ended(translation, recognizer.velocity(in: recognizer.view).x, false)
        case .cancelled, .failed: ended(translation, 0, true)
        default: break
        }
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var isOpen = false

        func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
            guard let pan = gestureRecognizer as? UIPanGestureRecognizer else { return false }
            let velocity = pan.velocity(in: pan.view)
            guard abs(velocity.x) > abs(velocity.y) * 1.25 else { return false }
            return isOpen ? velocity.x < 0 : velocity.x > 0
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool
        {
            var view = touch.view
            while let current = view {
                if current is UITextField || current is UISlider { return false }
                if let text = current as? UITextView, text.isEditable || text.selectedRange.length > 0 {
                    return false
                }
                view = current.superview
            }
            return true
        }
    }
}
