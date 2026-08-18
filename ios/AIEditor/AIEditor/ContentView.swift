import AVKit
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

enum AppPalette {
    static let green = Color(red: 0.18, green: 0.49, blue: 0.20)
    static let deepGreen = Color(red: 0.10, green: 0.31, blue: 0.16)
    static let yellow = Color(red: 0.98, green: 0.78, blue: 0.31)
    static let cream = Color(red: 1.00, green: 0.98, blue: 0.90)
}

struct ContentView: View {
    @StateObject private var model = EditorViewModel()
    @State private var sourceItem: PhotosPickerItem?
    @State private var addItem: PhotosPickerItem?
    @State private var prompt = ""
    @State private var audioImporter = false
    @State private var settings = false
    @State private var aiExpanded = true
    @State private var editsExpanded = false
    @State private var mediaExpanded = false

    var body: some View {
        Group {
            if model.project == nil { welcome } else { editor }
        }
        .background(AppPalette.cream.ignoresSafeArea())
        .tint(AppPalette.green)
        .alert("Something went wrong", isPresented: Binding(get: { model.errorMessage != nil }, set: { if !$0 { model.errorMessage = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(model.errorMessage ?? "")
        }
        .onChange(of: sourceItem) { _, item in if let item { model.create(from: item) } }
        .onChange(of: addItem) { _, item in if let item { model.add(from: item) } }
        .fileImporter(isPresented: $audioImporter, allowedContentTypes: [.audio]) { result in
            if case .success(let url) = result { model.addAudio(url) }
        }
        .sheet(isPresented: $settings) { ServerSettings() }
    }

    private var welcome: some View {
        ScrollView {
            VStack(spacing: 18) {
                VStack(alignment: .leading, spacing: 12) {
                    Image(systemName: "sparkles.rectangle.stack.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(.white)
                    Text("AI Media Editor")
                        .font(.largeTitle.bold())
                        .foregroundStyle(.white)
                    Text("Start with a photo or video. Chat with AI, review the plan, then fine-tune only what you need.")
                        .foregroundStyle(.white.opacity(0.94))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(24)
                .background(
                    LinearGradient(
                        colors: [AppPalette.green, AppPalette.green.opacity(0.82), AppPalette.yellow],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    in: RoundedRectangle(cornerRadius: 28)
                )

                VStack(spacing: 10) {
                    WelcomeStep(text: "Choose a photo or video", number: "1")
                    WelcomeStep(text: "Tell AI what you want", number: "2")
                    WelcomeStep(text: "Open only the section you need", number: "3")
                }

                PhotosPicker(selection: $sourceItem, matching: .any(of: [.images, .videos])) {
                    Label("Choose photo or video", systemImage: "plus.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(GreenButtonStyle())

                Button("Server settings") { settings = true }
                    .buttonStyle(YellowButtonStyle())

                if model.busy {
                    ProgressView(model.status)
                        .frame(maxWidth: .infinity)
                        .padding(16)
                        .background(.white, in: RoundedRectangle(cornerRadius: 18))
                }
            }
            .padding(20)
        }
        .safeAreaInset(edge: .bottom) { Color.clear.frame(height: 18) }
    }

    private var editor: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    PreviewHeader(model: model)
                        .clipShape(RoundedRectangle(cornerRadius: 24))
                        .overlay(RoundedRectangle(cornerRadius: 24).stroke(AppPalette.yellow.opacity(0.75), lineWidth: 2))

                    HStack(spacing: 10) {
                        Image(systemName: model.busy ? "hourglass.circle.fill" : "checkmark.circle.fill")
                            .foregroundStyle(model.busy ? AppPalette.yellow : AppPalette.green)
                        Text(model.status)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(AppPalette.deepGreen)
                        Spacer()
                    }
                    .padding(14)
                    .background(.white, in: RoundedRectangle(cornerRadius: 17))

                    AccordionSection(
                        title: "AI assistant",
                        subtitle: "Chat first, then review the plan",
                        accent: AppPalette.green,
                        isExpanded: $aiExpanded
                    ) {
                        aiPanel
                    }

                    AccordionSection(
                        title: "Edit controls",
                        subtitle: "Review and fine-tune AI changes",
                        accent: AppPalette.yellow,
                        isExpanded: $editsExpanded
                    ) {
                        editsPanel
                    }

                    AccordionSection(
                        title: "Media library",
                        subtitle: "Add photo, video, or music",
                        accent: AppPalette.green,
                        isExpanded: $mediaExpanded
                    ) {
                        mediaPanel
                    }
                }
                .padding(20)
            }
            .background(AppPalette.cream)
            .navigationTitle(model.project?.filename ?? "Project")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { settings = true } label: {
                        Image(systemName: "gearshape.fill")
                            .foregroundStyle(AppPalette.green)
                    }
                }
            }
            .safeAreaInset(edge: .bottom) { Color.clear.frame(height: 18) }
        }
    }

    private var aiPanel: some View {
        VStack(spacing: 12) {
            ForEach(model.messages) { message in
                HStack {
                    if message.role == "user" { Spacer(minLength: 28) }
                    Text(message.text)
                        .padding(12)
                        .foregroundStyle(AppPalette.deepGreen)
                        .background(
                            message.role == "user" ? AppPalette.yellow.opacity(0.30) : AppPalette.green.opacity(0.13),
                            in: RoundedRectangle(cornerRadius: 14)
                        )
                    if message.role != "user" { Spacer(minLength: 28) }
                }
            }

            VStack(spacing: 8) {
                ForEach(["Trim the beginning", "Add a title", "Put this in a star", "Add background music"], id: \.self) { example in
                    Button {
                        prompt = example
                    } label: {
                        HStack {
                            Image(systemName: "sparkles")
                            Text(example)
                            Spacer()
                        }
                    }
                    .buttonStyle(YellowButtonStyle())
                }
            }

            TextField("Describe the edit you want", text: $prompt, axis: .vertical)
                .lineLimit(2...4)
                .padding(13)
                .background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 15))

            Button {
                let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !text.isEmpty else { return }
                prompt = ""
                model.ask(text)
                aiExpanded = false
                editsExpanded = true
            } label: {
                Label("Ask AI", systemImage: "arrow.up.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(GreenButtonStyle())
            .disabled(prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.busy)
        }
    }

    private var editsPanel: some View {
        VStack(spacing: 12) {
            if model.draftOperations.isEmpty {
                ContentUnavailableView(
                    "No edits yet",
                    systemImage: "slider.horizontal.3",
                    description: Text("Ask AI for a change first.")
                )
                .frame(maxWidth: .infinity)
            } else {
                ForEach(model.draftOperations.indices, id: \.self) { index in
                    OperationCard(operation: $model.draftOperations[index], metadata: model.project!.metadata)
                }

                Button(model.proposal == nil ? "Render my changes" : "Apply AI changes") {
                    model.proposal == nil ? model.renderChanges() : model.applyProposal()
                }
                .buttonStyle(GreenButtonStyle())
            }
        }
    }

    private var mediaPanel: some View {
        VStack(spacing: 10) {
            PhotosPicker(selection: $addItem, matching: .any(of: [.images, .videos])) {
                Label("Add photo or video", systemImage: "plus.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(GreenButtonStyle())

            Button { audioImporter = true } label: {
                Label("Add background music", systemImage: "music.note")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(YellowButtonStyle())

            ForEach(model.project?.assets ?? []) { asset in
                HStack(spacing: 12) {
                    Image(systemName: asset.kind == "image" ? "photo" : asset.kind == "video" ? "video" : "music.note")
                        .foregroundStyle(AppPalette.green)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(asset.filename)
                            .foregroundStyle(AppPalette.deepGreen)
                        Text(asset.kind.capitalized)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .padding(13)
                .background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 14))
            }
        }
    }
}

struct WelcomeStep: View {
    let text: String
    let number: String

    var body: some View {
        HStack(spacing: 12) {
            Text(number)
                .font(.headline)
                .foregroundStyle(AppPalette.deepGreen)
                .frame(width: 34, height: 34)
                .background(AppPalette.yellow, in: Circle())
            Text(text)
                .foregroundStyle(AppPalette.deepGreen)
            Spacer()
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 17))
    }
}

struct AccordionSection<Content: View>: View {
    let title: String
    let subtitle: String
    let accent: Color
    @Binding var isExpanded: Bool
    let content: Content

    init(
        title: String,
        subtitle: String,
        accent: Color,
        isExpanded: Binding<Bool>,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.accent = accent
        self._isExpanded = isExpanded
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) { isExpanded.toggle() }
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(title)
                            .font(.headline)
                            .foregroundStyle(AppPalette.deepGreen)
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                        .font(.title3)
                        .foregroundStyle(accent)
                }
                .padding(16)
            }
            .buttonStyle(.plain)

            if isExpanded {
                content
                    .padding(.horizontal, 14)
                    .padding(.bottom, 14)
            }
        }
        .background(.white, in: RoundedRectangle(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(accent.opacity(0.55), lineWidth: 1.5))
    }
}

struct PreviewHeader: View {
    @ObservedObject var model: EditorViewModel
    @State private var url: URL?

    var body: some View {
        Group {
            if let url {
                if model.project?.previewUrl != nil || model.project?.sourceKind == "video" {
                    VideoPlayer(player: AVPlayer(url: url)).aspectRatio(16/9, contentMode: .fit)
                } else {
                    AsyncImage(url: url) { image in
                        image.resizable().scaledToFit()
                    } placeholder: {
                        ProgressView()
                    }
                    .aspectRatio(16/9, contentMode: .fit)
                }
            } else {
                Rectangle()
                    .fill(.black)
                    .aspectRatio(16/9, contentMode: .fit)
                    .overlay { ProgressView() }
            }
        }
        .background(.black)
        .task(id: model.project?.previewUrl ?? model.project?.sourceUrl) {
            url = await model.absolute(model.project?.previewUrl ?? model.project?.sourceUrl)
        }
    }
}

struct OperationCard: View {
    @Binding var operation: EditOperation
    let metadata: MediaMetadata
    @State private var expanded = false

    var visual: Bool {
        ["media_overlay", "picture_in_picture", "masked_media", "masked_video"].contains(operation.type)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(operation.displayTitle)
                        .font(.headline)
                        .foregroundStyle(AppPalette.deepGreen)
                    Text(summary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: $operation.enabled)
                    .labelsHidden()
                    .tint(AppPalette.green)
            }

            if expanded {
                if visual {
                    PlacementPad(operation: $operation, metadata: metadata)
                        .frame(height: 220)
                }
                if operation.type == "text_overlay" {
                    TextField("Text", text: Binding(get: { operation.text ?? "" }, set: { operation.text = $0 }))
                        .padding(12)
                        .background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 14))
                }
                if operation.type == "masked_media" || operation.type == "masked_video" {
                    Picker("Shape", selection: Binding(get: { operation.shape ?? "star" }, set: { operation.shape = $0 })) {
                        Text("Star").tag("star")
                        Text("Circle").tag("circle")
                        Text("Heart").tag("heart")
                        Text("Triangle").tag("triangle")
                    }
                    .pickerStyle(.segmented)
                }
            }

            Button(expanded ? "Done" : "Adjust") {
                withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
            }
            .buttonStyle(YellowButtonStyle())
        }
        .padding(14)
        .background(Color.white.opacity(0.75), in: RoundedRectangle(cornerRadius: 16))
    }

    var summary: String {
        if visual { return "Drag to position · \(operation.width ?? 360)×\(operation.height ?? 360)" }
        if operation.type == "text_overlay" { return operation.text ?? "Text" }
        if operation.type == "music" { return "Background audio" }
        return "Tap Adjust for details"
    }
}

struct PlacementPad: View {
    @Binding var operation: EditOperation
    let metadata: MediaMetadata

    var body: some View {
        GeometryReader { geo in
            let sourceW = Double(metadata.dimensions.width ?? 1280)
            let sourceH = Double(metadata.dimensions.height ?? 720)
            let scale = min(geo.size.width / sourceW, geo.size.height / sourceH)
            let w = CGFloat(operation.width ?? 360) * scale
            let h = CGFloat(operation.height ?? 360) * scale

            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 14).fill(.black.opacity(0.86))
                RoundedRectangle(cornerRadius: 14).stroke(AppPalette.yellow.opacity(0.60))
                RoundedRectangle(cornerRadius: operation.shape == "circle" ? min(w, h) / 2 : 14)
                    .fill(AppPalette.green.opacity(0.32))
                    .overlay {
                        Image(systemName: operation.type.contains("masked") ? "star.fill" : "photo")
                            .foregroundStyle(.white)
                    }
                    .frame(width: max(36, w), height: max(36, h))
                    .offset(x: CGFloat(operation.x ?? 40) * scale, y: CGFloat(operation.y ?? 40) * scale)
                    .gesture(DragGesture().onChanged { value in
                        operation.x = Int(value.location.x / scale - w / (2 * scale))
                        operation.y = Int(value.location.y / scale - h / (2 * scale))
                    })
            }
            .overlay(alignment: .bottom) {
                HStack {
                    Button("Smaller") {
                        operation.width = max(32, (operation.width ?? 360) - 40)
                        operation.height = max(32, (operation.height ?? 360) - 40)
                    }
                    Spacer()
                    Text("Drag to move")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Larger") {
                        operation.width = min(4096, (operation.width ?? 360) + 40)
                        operation.height = min(4096, (operation.height ?? 360) + 40)
                    }
                }
                .padding(8)
                .background(.ultraThinMaterial)
            }
        }
    }
}

struct GreenButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .padding(.vertical, 14)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .background(AppPalette.green, in: RoundedRectangle(cornerRadius: 16))
            .opacity(configuration.isPressed ? 0.84 : 1)
    }
}

struct YellowButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(AppPalette.deepGreen)
            .padding(.vertical, 12)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity)
            .background(AppPalette.yellow.opacity(0.34), in: RoundedRectangle(cornerRadius: 15))
            .overlay(RoundedRectangle(cornerRadius: 15).stroke(AppPalette.yellow.opacity(0.8), lineWidth: 1))
            .opacity(configuration.isPressed ? 0.82 : 1)
    }
}

struct ServerSettings: View {
    private static let defaultServer = "https://ai-generator-for-video-git-279005246322.europe-west2.run.app"

    @Environment(\.dismiss) private var dismiss
    @State private var url: String

    init() {
        let saved = UserDefaults.standard.string(forKey: "serverURL")
        _url = State(initialValue: Self.normalized(saved))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend server") {
                    TextField("https://…", text: $url)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    Text("Cloud Run is already configured as the default. You normally do not need to change this.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Button("Use Cloud Run") {
                        url = Self.defaultServer
                    }
                    .foregroundStyle(AppPalette.green)
                }
            }
            .navigationTitle("Settings")
            .onAppear {
                UserDefaults.standard.set(Self.normalized(url), forKey: "serverURL")
            }
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let value = Self.normalized(url)
                        UserDefaults.standard.set(value, forKey: "serverURL")
                        dismiss()
                    }
                }
            }
        }
    }

    private static func normalized(_ value: String?) -> String {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/")) ?? ""
        let lower = trimmed.lowercased()
        if trimmed.isEmpty ||
            lower.hasPrefix("http://localhost") ||
            lower.hasPrefix("https://localhost") ||
            lower.hasPrefix("http://127.0.0.1") ||
            lower.hasPrefix("https://127.0.0.1") ||
            lower.hasPrefix("http://10.0.2.2") ||
            lower.hasPrefix("https://10.0.2.2") {
            return defaultServer
        }
        return trimmed
    }
}
