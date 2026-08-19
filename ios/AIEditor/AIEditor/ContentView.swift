import AVKit
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

enum AppPalette {
    static let green = Color(red: 0.18, green: 0.49, blue: 0.20)
    static let deepGreen = Color(red: 0.10, green: 0.31, blue: 0.16)
    static let yellow = Color(red: 0.98, green: 0.78, blue: 0.31)
    static let cream = Color(red: 1.00, green: 0.98, blue: 0.90)
    static let mint = Color(red: 0.88, green: 0.96, blue: 0.87)
    static let butter = Color(red: 1.00, green: 0.95, blue: 0.73)
    static let pale = Color(red: 0.98, green: 0.99, blue: 0.96)
}

private enum ManualTool: String, CaseIterable, Identifiable {
    case trim, speed, volume, mute, text, split, join, pip, overlay, shape, music, style
    var id: String { rawValue }

    var title: String {
        switch self {
        case .trim: "Trim"
        case .speed: "Speed"
        case .volume: "Volume"
        case .mute: "Mute"
        case .text: "Text"
        case .split: "Split"
        case .join: "Join"
        case .pip: "PiP"
        case .overlay: "Overlay"
        case .shape: "Shape"
        case .music: "Music"
        case .style: "Style"
        }
    }

    var subtitle: String {
        switch self {
        case .trim: "Start / end"
        case .speed: "0.5× – 2×"
        case .volume: "Sound level"
        case .mute: "Silence source"
        case .text: "Title / caption"
        case .split: "Two-up layout"
        case .join: "Clip after clip"
        case .pip: "Small media"
        case .overlay: "Layer on top"
        case .shape: "Star / heart"
        case .music: "Background audio"
        case .style: "Generative look"
        }
    }

    var icon: String {
        switch self {
        case .trim: "scissors"
        case .speed: "gauge.with.dots.needle.67percent"
        case .volume: "speaker.wave.2.fill"
        case .mute: "speaker.slash.fill"
        case .text: "textformat"
        case .split: "rectangle.split.2x1.fill"
        case .join: "rectangle.connected.to.line.below"
        case .pip: "pip.fill"
        case .overlay: "square.stack.3d.up.fill"
        case .shape: "star.fill"
        case .music: "music.note"
        case .style: "paintbrush.pointed.fill"
        }
    }
}

struct ContentView: View {
    @StateObject private var model = EditorViewModel()
    @State private var sourceItem: PhotosPickerItem?
    @State private var addItem: PhotosPickerItem?
    @State private var prompt = ""
    @State private var audioImporter = false
    @State private var settings = false

    @State private var toolsExpanded = true
    @State private var aiExpanded = false
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
                    Text("Edit directly with simple tools, or ask AI when you want a helping hand.")
                        .foregroundStyle(.white.opacity(0.94))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(24)
                .background(
                    LinearGradient(colors: [AppPalette.green, AppPalette.green.opacity(0.82), AppPalette.yellow], startPoint: .topLeading, endPoint: .bottomTrailing),
                    in: RoundedRectangle(cornerRadius: 30)
                )

                VStack(spacing: 10) {
                    WelcomeStep(text: "Choose a photo or video", number: "1")
                    WelcomeStep(text: "Use Quick tools or Ask AI", number: "2")
                    WelcomeStep(text: "Review, adjust, then render", number: "3")
                }

                PhotosPicker(selection: $sourceItem, matching: .any(of: [.images, .videos])) {
                    Label(model.busy ? model.status : "Choose photo or video", systemImage: model.busy ? "hourglass" : "plus.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(CutePrimaryButtonStyle())
                .disabled(model.busy)

                Button("Server settings") { settings = true }
                    .buttonStyle(CuteSecondaryButtonStyle())
                    .disabled(model.busy)

                if model.busy {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("\(model.status)… Please wait")
                    }
                    .frame(maxWidth: .infinity)
                    .padding(16)
                    .background(.white, in: RoundedRectangle(cornerRadius: 18))
                }
            }
            .padding(20)
        }
        .safeAreaInset(edge: .bottom) { Color.clear.frame(height: 20) }
    }

    private var editor: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    PreviewHeader(model: model)
                        .clipShape(RoundedRectangle(cornerRadius: 24))
                        .overlay(RoundedRectangle(cornerRadius: 24).stroke(AppPalette.yellow.opacity(0.75), lineWidth: 2))

                    statusBanner

                    AccordionSection(title: "Quick tools", subtitle: "Edit directly without asking AI", accent: AppPalette.green, isExpanded: $toolsExpanded) {
                        manualToolsPanel
                    }

                    AccordionSection(title: "AI assistant", subtitle: "Describe an edit in your own words", accent: AppPalette.yellow, isExpanded: $aiExpanded) {
                        aiPanel
                    }

                    AccordionSection(title: "Edit controls", subtitle: "Fine-tune every active change", accent: AppPalette.green, isExpanded: $editsExpanded) {
                        editsPanel
                    }

                    AccordionSection(title: "Media library", subtitle: "Add another clip, photo, or music", accent: AppPalette.yellow, isExpanded: $mediaExpanded) {
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
                        Image(systemName: "gearshape.fill").foregroundStyle(AppPalette.green)
                    }
                    .disabled(model.busy)
                }
            }
            .safeAreaInset(edge: .bottom) { Color.clear.frame(height: 20) }
        }
    }

    private var statusBanner: some View {
        HStack(spacing: 10) {
            if model.busy {
                ProgressView().tint(AppPalette.green)
            } else {
                Image(systemName: model.status == "Failed" ? "exclamationmark.circle.fill" : "checkmark.circle.fill")
                    .foregroundStyle(model.status == "Failed" ? .red : AppPalette.green)
            }
            Text(model.busy ? "\(model.status)… Please wait" : model.status)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(AppPalette.deepGreen)
            Spacer()
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 17))
    }

    private var manualToolsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Pick a tool, set or adjust the values, then render. AI is optional.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                ForEach(Array(ManualTool.allCases.enumerated()), id: \.element.id) { index, tool in
                    Button {
                        addManualTool(tool)
                    } label: {
                        VStack(spacing: 7) {
                            Image(systemName: tool.icon)
                                .font(.title2)
                            Text(tool.title)
                                .font(.headline)
                            Text(tool.subtitle)
                                .font(.caption2)
                                .foregroundStyle(AppPalette.deepGreen.opacity(0.72))
                        }
                        .frame(maxWidth: .infinity, minHeight: 88)
                    }
                    .buttonStyle(CuteToolButtonStyle(background: index.isMultiple(of: 2) ? AppPalette.mint : AppPalette.butter))
                    .disabled(model.busy)
                }
            }
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
                        .background(message.role == "user" ? AppPalette.yellow.opacity(0.30) : AppPalette.green.opacity(0.13), in: RoundedRectangle(cornerRadius: 14))
                    if message.role != "user" { Spacer(minLength: 28) }
                }
            }

            ForEach(["Trim the beginning", "Add a title", "Join the two videos", "Put the second clip beside the first"], id: \.self) { example in
                Button {
                    prompt = example
                } label: {
                    HStack {
                        Image(systemName: "sparkles")
                        Text(example)
                        Spacer()
                    }
                }
                .buttonStyle(CuteSecondaryButtonStyle())
                .disabled(model.busy)
            }

            TextField("Describe the edit you want", text: $prompt, axis: .vertical)
                .lineLimit(2...4)
                .padding(13)
                .background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 15))
                .disabled(model.busy)

            Button {
                let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !text.isEmpty else { return }
                prompt = ""
                model.ask(text)
                aiExpanded = false
                editsExpanded = true
            } label: {
                HStack(spacing: 9) {
                    if model.busy && model.status == "AI is planning" { ProgressView().tint(.white) }
                    Image(systemName: "arrow.up.circle.fill")
                    Text(model.busy && model.status == "AI is planning" ? "AI is planning…" : "Ask AI")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(CutePrimaryButtonStyle())
            .disabled(prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.busy)
        }
    }

    private var editsPanel: some View {
        VStack(spacing: 12) {
            if model.draftOperations.isEmpty {
                VStack(spacing: 9) {
                    Image(systemName: "slider.horizontal.3")
                        .font(.title2)
                        .foregroundStyle(AppPalette.green)
                    Text("No edits yet")
                        .font(.headline)
                    Text("Add a Quick tool or ask AI for a change.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(24)
                .background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 17))
            } else {
                ForEach(model.draftOperations.indices, id: \.self) { index in
                    OperationCard(
                        operation: $model.draftOperations[index],
                        metadata: model.project!.metadata,
                        assets: model.project?.assets ?? [],
                        onRemove: { model.removeOperation(at: index) }
                    )
                }

                Button {
                    model.proposal == nil ? model.renderChanges() : model.applyProposal()
                } label: {
                    HStack(spacing: 9) {
                        if model.busy && model.status == "Rendering" { ProgressView().tint(.white) }
                        Image(systemName: "wand.and.stars.inverse")
                        Text(model.busy && model.status == "Rendering" ? "Rendering… Please wait" : (model.proposal == nil ? "Render my changes" : "Apply AI changes"))
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(CutePrimaryButtonStyle())
                .disabled(model.busy)
            }
        }
    }

    private var mediaPanel: some View {
        VStack(spacing: 10) {
            PhotosPicker(selection: $addItem, matching: .any(of: [.images, .videos])) {
                Label("Add photo or video", systemImage: "plus.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(CutePrimaryButtonStyle())
            .disabled(model.busy)

            Button { audioImporter = true } label: {
                Label("Add background music", systemImage: "music.note")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(CuteSecondaryButtonStyle())
            .disabled(model.busy)

            ForEach(Array((model.project?.assets ?? []).enumerated()), id: \.element.id) { index, asset in
                HStack(spacing: 12) {
                    Image(systemName: asset.kind == "image" ? "photo.fill" : asset.kind == "video" ? "video.fill" : "music.note")
                        .foregroundStyle(AppPalette.green)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(asset.filename).foregroundStyle(AppPalette.deepGreen)
                        Text(asset.kind.capitalized).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .padding(13)
                .background(index.isMultiple(of: 2) ? AppPalette.mint : AppPalette.butter, in: RoundedRectangle(cornerRadius: 15))
            }
        }
    }

    private func addManualTool(_ tool: ManualTool) {
        guard let project = model.project else { return }
        let visuals = project.assets.filter { $0.kind == "image" || $0.kind == "video" }
        let videos = project.assets.filter { $0.kind == "video" }
        let audio = project.assets.filter { $0.kind == "audio" }
        let duration = max(0.5, project.metadata.durationSeconds)
        let operation: EditOperation?

        switch tool {
        case .trim:
            operation = EditOperation(type: "trim", startSeconds: 0, endSeconds: max(0.5, duration - min(1, duration * 0.2)))
        case .speed:
            operation = EditOperation(type: "speed", speed: 1.25)
        case .volume:
            operation = EditOperation(type: "volume", volume: 1)
        case .mute:
            operation = EditOperation(type: "mute")
        case .text:
            operation = EditOperation(type: "text_overlay", text: "Your title", position: "bottom", fontSize: 48)
        case .split:
            guard let asset = visuals.first else { return showMissing("Add a second photo or video in Media library first.") }
            operation = EditOperation(type: "split_screen", secondaryAssetId: asset.id, layout: "side_by_side", ratio: 0.5)
        case .join:
            guard let asset = videos.first else { return showMissing("Add a second video in Media library first.") }
            operation = EditOperation(type: "concat", secondaryAssetId: asset.id)
        case .pip:
            guard let asset = visuals.first else { return showMissing("Add a second photo or video in Media library first.") }
            operation = EditOperation(type: "picture_in_picture", secondaryAssetId: asset.id, x: 40, y: 40, width: 360, height: 240)
        case .overlay:
            guard let asset = visuals.first else { return showMissing("Add a second photo or video in Media library first.") }
            operation = EditOperation(type: "media_overlay", sourceAssetId: asset.id, x: 40, y: 40, width: 360, height: 240)
        case .shape:
            guard let asset = visuals.first else { return showMissing("Add a second photo or video in Media library first.") }
            operation = EditOperation(type: "masked_media", sourceAssetId: asset.id, shape: "star", x: 40, y: 40, width: 360, height: 360)
        case .music:
            guard let asset = audio.first else { return showMissing("Add an audio file in Media library first.") }
            operation = EditOperation(type: "music", sourceAssetId: asset.id, volume: 0.35, fadeInSeconds: 0.5, fadeOutSeconds: 0.5, loop: true, ducking: false)
        case .style:
            operation = EditOperation(type: "style_transfer", stylePrompt: "soft colorful illustration")
        }

        if let operation {
            model.addManualOperation(operation)
            toolsExpanded = false
            aiExpanded = false
            editsExpanded = true
        }
    }

    private func showMissing(_ message: String) {
        model.errorMessage = message
        mediaExpanded = true
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
            Text(text).foregroundStyle(AppPalette.deepGreen)
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

    init(title: String, subtitle: String, accent: Color, isExpanded: Binding<Bool>, @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.accent = accent
        self._isExpanded = isExpanded
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.spring(response: 0.28, dampingFraction: 0.88)) { isExpanded.toggle() }
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(title).font(.headline).foregroundStyle(AppPalette.deepGreen)
                        Text(subtitle).font(.caption).foregroundStyle(.secondary)
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
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(.white, in: RoundedRectangle(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(accent.opacity(0.55), lineWidth: 1.5))
        .shadow(color: .black.opacity(0.04), radius: 8, y: 4)
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
                    AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { ProgressView() }
                        .aspectRatio(16/9, contentMode: .fit)
                }
            } else {
                Rectangle().fill(.black).aspectRatio(16/9, contentMode: .fit).overlay { ProgressView() }
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
    let assets: [MediaAsset]
    let onRemove: () -> Void
    @State private var expanded = false

    private var visualAssets: [MediaAsset] { assets.filter { $0.kind == "image" || $0.kind == "video" } }
    private var videoAssets: [MediaAsset] { assets.filter { $0.kind == "video" } }
    private var audioAssets: [MediaAsset] { assets.filter { $0.kind == "audio" } }
    private var visual: Bool { ["media_overlay", "picture_in_picture", "masked_media", "masked_video"].contains(operation.type) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(operation.displayTitle).font(.headline).foregroundStyle(AppPalette.deepGreen)
                    Text(summary).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: $operation.enabled).labelsHidden().tint(AppPalette.green)
            }

            if expanded {
                detailControls
            }

            HStack(spacing: 8) {
                Button(expanded ? "Done" : "Adjust") {
                    withAnimation(.spring(response: 0.25, dampingFraction: 0.9)) { expanded.toggle() }
                }
                .buttonStyle(CuteMintButtonStyle())

                Button("Remove", role: .destructive, action: onRemove)
                    .buttonStyle(CuteSecondaryButtonStyle())
            }
        }
        .padding(14)
        .background(AppPalette.pale, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(AppPalette.green.opacity(0.18)))
    }

    @ViewBuilder private var detailControls: some View {
        switch operation.type {
        case "trim":
            let duration = max(0.5, metadata.durationSeconds)
            VStack(alignment: .leading, spacing: 8) {
                Text("Start: \(format(operation.startSeconds ?? 0))s").font(.caption).foregroundStyle(AppPalette.deepGreen)
                Slider(value: Binding(get: { operation.startSeconds ?? 0 }, set: { operation.startSeconds = min($0, (operation.endSeconds ?? duration) - 0.1) }), in: 0...max(0.1, duration - 0.1))
                Text("End: \(format(operation.endSeconds ?? duration))s").font(.caption).foregroundStyle(AppPalette.deepGreen)
                Slider(value: Binding(get: { operation.endSeconds ?? duration }, set: { operation.endSeconds = max($0, (operation.startSeconds ?? 0) + 0.1) }), in: 0.1...duration)
            }
        case "speed":
            sliderControl("Speed", value: Binding(get: { operation.speed ?? 1 }, set: { operation.speed = $0 }), range: 0.5...2, suffix: "×")
        case "volume":
            sliderControl("Source volume", value: Binding(get: { operation.volume ?? 1 }, set: { operation.volume = $0 }), range: 0...4, suffix: "×")
        case "mute":
            Text("Source audio will be muted.").font(.caption).foregroundStyle(.secondary)
        case "text_overlay":
            VStack(spacing: 9) {
                TextField("Text", text: Binding(get: { operation.text ?? "" }, set: { operation.text = $0 }))
                    .padding(11).background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 13))
                Picker("Position", selection: Binding(get: { operation.position ?? "bottom" }, set: { operation.position = $0 })) {
                    Text("Top").tag("top"); Text("Center").tag("center"); Text("Bottom").tag("bottom")
                }.pickerStyle(.segmented)
                sliderControl("Text size", value: Binding(get: { Double(operation.fontSize ?? 48) }, set: { operation.fontSize = Int($0) }), range: 8...120, suffix: "")
            }
        case "split_screen":
            VStack(spacing: 9) {
                assetPicker(label: "Second media", assets: visualAssets, selection: Binding(get: { operation.secondaryAssetId ?? visualAssets.first?.id ?? "" }, set: { operation.secondaryAssetId = $0 }))
                Picker("Layout", selection: Binding(get: { operation.layout ?? "side_by_side" }, set: { operation.layout = $0 })) {
                    Text("Side by side").tag("side_by_side"); Text("Stacked").tag("stacked")
                }.pickerStyle(.segmented)
            }
        case "concat":
            assetPicker(label: "Second video", assets: videoAssets, selection: Binding(get: { operation.secondaryAssetId ?? videoAssets.first?.id ?? "" }, set: { operation.secondaryAssetId = $0 }))
        case "picture_in_picture", "masked_video":
            VStack(spacing: 9) {
                assetPicker(label: "Media", assets: visualAssets, selection: Binding(get: { operation.secondaryAssetId ?? visualAssets.first?.id ?? "" }, set: { operation.secondaryAssetId = $0 }))
                PlacementPad(operation: $operation, metadata: metadata).frame(height: 220)
                shapePickerIfNeeded
            }
        case "media_overlay", "masked_media":
            VStack(spacing: 9) {
                assetPicker(label: "Media", assets: visualAssets, selection: Binding(get: { operation.sourceAssetId ?? visualAssets.first?.id ?? "" }, set: { operation.sourceAssetId = $0 }))
                PlacementPad(operation: $operation, metadata: metadata).frame(height: 220)
                shapePickerIfNeeded
            }
        case "music":
            VStack(spacing: 9) {
                assetPicker(label: "Audio", assets: audioAssets, selection: Binding(get: { operation.sourceAssetId ?? audioAssets.first?.id ?? "" }, set: { operation.sourceAssetId = $0 }))
                sliderControl("Music volume", value: Binding(get: { operation.volume ?? 0.35 }, set: { operation.volume = $0 }), range: 0...1, suffix: "")
                Toggle("Lower music while speech plays", isOn: Binding(get: { operation.ducking ?? false }, set: { operation.ducking = $0 })).tint(AppPalette.green)
            }
        case "style_transfer":
            TextField("Describe the visual style", text: Binding(get: { operation.stylePrompt ?? "" }, set: { operation.stylePrompt = $0 }), axis: .vertical)
                .lineLimit(2...4).padding(11).background(AppPalette.cream, in: RoundedRectangle(cornerRadius: 13))
        default:
            Text("This edit is ready to render.").font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder private var shapePickerIfNeeded: some View {
        if operation.type == "masked_media" || operation.type == "masked_video" {
            Picker("Shape", selection: Binding(get: { operation.shape ?? "star" }, set: { operation.shape = $0 })) {
                Text("Star").tag("star"); Text("Circle").tag("circle"); Text("Heart").tag("heart"); Text("Triangle").tag("triangle")
            }.pickerStyle(.segmented)
        }
    }

    private func sliderControl(_ title: String, value: Binding<Double>, range: ClosedRange<Double>, suffix: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("\(title): \(String(format: "%.2f", value.wrappedValue))\(suffix)").font(.caption).foregroundStyle(AppPalette.deepGreen)
            Slider(value: value, in: range)
        }
    }

    private func assetPicker(label: String, assets: [MediaAsset], selection: Binding<String>) -> some View {
        Group {
            if assets.isEmpty {
                Text("No compatible media uploaded").font(.caption).foregroundStyle(.secondary)
            } else {
                Picker(label, selection: selection) {
                    ForEach(assets) { asset in Text(asset.filename).tag(asset.id) }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var summary: String {
        switch operation.type {
        case "trim": return "\(format(operation.startSeconds ?? 0))s → \(format(operation.endSeconds ?? metadata.durationSeconds))s"
        case "speed": return "\(String(format: "%.2f", operation.speed ?? 1))× playback"
        case "volume": return "\(Int((operation.volume ?? 1) * 100))% source volume"
        case "mute": return "Source audio off"
        case "text_overlay": return operation.text ?? "Text"
        case "split_screen": return operation.layout == "stacked" ? "Two media stacked" : "Two media side by side"
        case "concat": return "Append another video"
        case "music": return "Background audio · \(Int((operation.volume ?? 0.35) * 100))%"
        case "style_transfer": return operation.stylePrompt ?? "Generative visual style"
        default:
            return visual ? "Drag to position · \(operation.width ?? 360)×\(operation.height ?? 360)" : "Tap Adjust for details"
        }
    }

    private func format(_ value: Double) -> String {
        abs(value - value.rounded()) < 0.001 ? String(Int(value)) : String(format: "%.2f", value)
    }
}

struct PlacementPad: View {
    @Binding var operation: EditOperation
    let metadata: MediaMetadata

    var body: some View {
        GeometryReader { geo in
            let sourceW = max(1, Double(metadata.dimensions.width ?? 1280))
            let sourceH = max(1, Double(metadata.dimensions.height ?? 720))
            let scale = max(0.0001, min(geo.size.width / sourceW, geo.size.height / sourceH))
            let w = CGFloat(operation.width ?? 360) * scale
            let h = CGFloat(operation.height ?? 360) * scale

            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 14).fill(.black.opacity(0.86))
                RoundedRectangle(cornerRadius: 14).stroke(AppPalette.yellow.opacity(0.60))
                RoundedRectangle(cornerRadius: operation.shape == "circle" ? min(w, h) / 2 : 14)
                    .fill(AppPalette.green.opacity(0.34))
                    .overlay {
                        Image(systemName: operation.type.contains("masked") ? "star.fill" : "photo.fill").foregroundStyle(.white)
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
                    Text("Drag to move").font(.caption).foregroundStyle(.secondary)
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

struct CutePrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .padding(.vertical, 14)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .background(LinearGradient(colors: [AppPalette.green, AppPalette.green.opacity(0.82)], startPoint: .leading, endPoint: .trailing), in: RoundedRectangle(cornerRadius: 17))
            .shadow(color: AppPalette.green.opacity(0.16), radius: configuration.isPressed ? 2 : 7, y: configuration.isPressed ? 1 : 4)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.82 : 1)
            .animation(.easeOut(duration: 0.09), value: configuration.isPressed)
    }
}

struct CuteSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(AppPalette.deepGreen)
            .padding(.vertical, 12)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity)
            .background(AppPalette.butter, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppPalette.yellow.opacity(0.75), lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.80 : 1)
            .animation(.easeOut(duration: 0.09), value: configuration.isPressed)
    }
}

struct CuteMintButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(AppPalette.deepGreen)
            .padding(.vertical, 12)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity)
            .background(AppPalette.mint, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppPalette.green.opacity(0.28), lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.82 : 1)
    }
}

struct CuteToolButtonStyle: ButtonStyle {
    let background: Color
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(AppPalette.deepGreen)
            .padding(8)
            .background(background, in: RoundedRectangle(cornerRadius: 20))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(AppPalette.green.opacity(0.16), lineWidth: 1))
            .shadow(color: .black.opacity(0.035), radius: configuration.isPressed ? 2 : 6, y: configuration.isPressed ? 1 : 3)
            .scaleEffect(configuration.isPressed ? 0.95 : 1)
            .animation(.spring(response: 0.18, dampingFraction: 0.72), value: configuration.isPressed)
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
                    Text("Cloud Run is already configured. You normally do not need to change this.")
                        .font(.caption).foregroundStyle(.secondary)
                    Button("Use Cloud Run") { url = Self.defaultServer }.foregroundStyle(AppPalette.green)
                }
            }
            .navigationTitle("Settings")
            .onAppear { UserDefaults.standard.set(Self.normalized(url), forKey: "serverURL") }
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        UserDefaults.standard.set(Self.normalized(url), forKey: "serverURL")
                        dismiss()
                    }
                }
            }
        }
    }

    private static func normalized(_ value: String?) -> String {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/")) ?? ""
        let lower = trimmed.lowercased()
        if trimmed.isEmpty || lower.hasPrefix("http://localhost") || lower.hasPrefix("https://localhost") || lower.hasPrefix("http://127.0.0.1") || lower.hasPrefix("https://127.0.0.1") || lower.hasPrefix("http://10.0.2.2") || lower.hasPrefix("https://10.0.2.2") {
            return defaultServer
        }
        return trimmed
    }
}
