import SwiftUI

@main
struct AIEditorApp: App {
    var body: some Scene {
        WindowGroup {
            DepthScene {
                ContentView()
            }
        }
    }
}

/// Adds a subtle light-from-top-left / shadow-to-bottom-right treatment across
/// the existing cards and controls. Individual editor controls keep their own
/// shadows, while this global gloss makes the whole interface feel more raised.
struct DepthScene<Content: View>: View {
    @ViewBuilder let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .overlay {
                LinearGradient(
                    colors: [
                        Color.white.opacity(0.10),
                        Color.clear,
                        Color(red: 0.08, green: 0.24, blue: 0.12).opacity(0.045)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                .blendMode(.softLight)
                .allowsHitTesting(false)
            }
            .overlay(alignment: .topLeading) {
                RadialGradient(
                    colors: [Color.white.opacity(0.11), .clear],
                    center: .topLeading,
                    startRadius: 8,
                    endRadius: 260
                )
                .frame(width: 280, height: 280)
                .offset(x: -80, y: -70)
                .allowsHitTesting(false)
            }
            .preferredColorScheme(.light)
    }
}
