import SwiftUI

/// Colors follow frontend/src/app/globals.css. Glass comes from system navigation chrome.
enum SodAIStyle {
    static let ink = Color(
        uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.961, green: 0.961, blue: 0.969, alpha: 1)
                : UIColor(red: 0.114, green: 0.114, blue: 0.122, alpha: 1)
        })
    static let canvas = Color(uiColor: .systemBackground)
    static let surface = Color(uiColor: .secondarySystemGroupedBackground)
    static let secondary = Color(uiColor: .secondarySystemBackground)
    static let border = Color(uiColor: .separator)
    static let bottomControlHeight: CGFloat = 56
}
