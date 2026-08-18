import AVKit
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var model = EditorViewModel()
    @State private var sourceItem: PhotosPickerItem?
    @State private var addItem: PhotosPickerItem?
    @State private var prompt = ""
    @State private var audioImporter = false
    @State private var settings = false

    var body: some View {
        Group {
            if model.project == nil { welcome } else { editor }
        }
        .alert("Something went wrong", isPresented: Binding(get: { model.errorMessage != nil }, set: { if !$0 { model.errorMessage = nil } })) {
            Button("OK", role: .cancel) {}
        } message: { Text(model.errorMessage ?? "") }
        .onChange(of: sourceItem) { _, item in if let item { model.create(from: item) } }
        .onChange(of: addItem) { _, item in if let item { model.add(from: item) } }
        .fileImporter(isPresented: $audioImporter, allowedContentTypes: [.audio]) { result in if case .success(let url) = result { model.addAudio(url) } }
        .sheet(isPresented: $settings) { ServerSettings() }
    }

    private var welcome: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "wand.and.stars").font(.system(size: 52)).foregroundStyle(.tint)
            VStack(spacing: 8) {
                Text("AI Video Editor").font(.largeTitle.bold())
                Text("Start with a photo or video. AI makes the first edit; you stay in control.").multilineTextAlignment(.center).foregroundStyle(.secondary)
            }
            PhotosPicker(selection: $sourceItem, matching: .any(of: [.images, .videos])) {
                Label("Choose photo or video", systemImage: "photo.on.rectangle.angled").frame(maxWidth: .infinity).padding(.vertical, 8)
            }.buttonStyle(.borderedProminent).controlSize(.large)
            Button("Server settings") { settings = true }.buttonStyle(.plain).foregroundStyle(.secondary)
            Spacer()
        }
        .padding(24)
        .overlay { if model.busy { ProgressView(model.status).padding(24).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18)) } }
    }

    private var editor: some View {
        NavigationStack {
            VStack(spacing: 0) {
                PreviewHeader(model: model)
                TabView(selection: $model.selectedTab) {
                    aiTab.tag(0).tabItem { Label("AI", systemImage: "sparkles") }
                    editsTab.tag(1).tabItem { Label("Edits", systemImage: "slider.horizontal.3") }
                    mediaTab.tag(2).tabItem { Label("Media", systemImage: "photo.stack") }
                }
            }
            .navigationTitle(model.project?.filename ?? "Project")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { settings = true } label: { Image(systemName: "gearshape") } } }
            .overlay(alignment: .top) { if model.busy { ProgressView(model.status).padding(10).background(.thinMaterial, in: Capsule()).padding(.top, 8) } }
        }
    }

    private var aiTab: some View {
        VStack(spacing: 12) {
            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(model.messages) { msg in
                        HStack {
                            if msg.role == "user" { Spacer() }
                            Text(msg.text).padding(12).background(msg.role == "user" ? Color.accentColor.opacity(0.16) : Color.secondary.opacity(0.12), in: RoundedRectangle(cornerRadius: 14))
                            if msg.role != "user" { Spacer() }
                        }
                    }
                }.padding()
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(["Trim the beginning", "Add a title", "Put this in a star", "Add background music"], id: \.self) { example in
                        Button(example) { prompt = example }.buttonStyle(.bordered)
                    }
                }.padding(.horizontal)
            }
            HStack(alignment: .bottom) {
                TextField("Describe the edit you want", text: $prompt, axis: .vertical).textFieldStyle(.roundedBorder)
                Button { let p = prompt; prompt = ""; model.ask(p) } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                    .disabled(prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.busy)
            }.padding()
        }
    }

    private var editsTab: some View {
        VStack(spacing: 0) {
            if model.draftOperations.isEmpty {
                ContentUnavailableView("No edits yet", systemImage: "slider.horizontal.3", description: Text("Ask AI for a change first."))
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(model.draftOperations.indices, id: \.self) { index in
                            OperationCard(operation: $model.draftOperations[index], metadata: model.project!.metadata)
                        }
                    }.padding()
                }
            }
            if !model.draftOperations.isEmpty {
                Button(model.proposal == nil ? "Render my changes" : "Apply AI changes") {
                    model.proposal == nil ? model.renderChanges() : model.applyProposal()
                }.buttonStyle(.borderedProminent).controlSize(.large).frame(maxWidth: .infinity).padding()
            }
        }
    }

    private var mediaTab: some View {
        VStack(spacing: 16) {
            HStack {
                PhotosPicker(selection: $addItem, matching: .any(of: [.images, .videos])) { Label("Add photo/video", systemImage: "plus") }.buttonStyle(.borderedProminent)
                Button { audioImporter = true } label: { Label("Add music", systemImage: "music.note") }.buttonStyle(.bordered)
            }.padding(.top)
            List(model.project?.assets ?? []) { asset in
                HStack {
                    Image(systemName: asset.kind == "image" ? "photo" : asset.kind == "video" ? "video" : "music.note")
                    VStack(alignment: .leading) { Text(asset.filename); Text(asset.kind.capitalized).font(.caption).foregroundStyle(.secondary) }
                }
            }
        }.padding(.horizontal)
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
                    AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { ProgressView() }.aspectRatio(16/9, contentMode: .fit)
                }
            } else { Rectangle().fill(.black).aspectRatio(16/9, contentMode: .fit).overlay { ProgressView() } }
        }
        .background(.black)
        .task(id: model.project?.previewUrl ?? model.project?.sourceUrl) { url = await model.absolute(model.project?.previewUrl ?? model.project?.sourceUrl) }
    }
}

struct OperationCard: View {
    @Binding var operation: EditOperation
    let metadata: MediaMetadata
    @State private var expanded = false
    var visual: Bool { ["media_overlay", "picture_in_picture", "masked_media", "masked_video"].contains(operation.type) }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading) { Text(operation.displayTitle).font(.headline); Text(summary).font(.caption).foregroundStyle(.secondary) }
                Spacer(); Toggle("", isOn: $operation.enabled).labelsHidden()
            }
            if expanded {
                if visual { PlacementPad(operation: $operation, metadata: metadata).frame(height: 220) }
                if operation.type == "text_overlay" { TextField("Text", text: Binding(get: { operation.text ?? "" }, set: { operation.text = $0 })).textFieldStyle(.roundedBorder) }
                if operation.type == "masked_media" || operation.type == "masked_video" {
                    Picker("Shape", selection: Binding(get: { operation.shape ?? "star" }, set: { operation.shape = $0 })) {
                        Text("Star").tag("star"); Text("Circle").tag("circle"); Text("Heart").tag("heart"); Text("Triangle").tag("triangle")
                    }.pickerStyle(.segmented)
                }
            }
            Button(expanded ? "Done" : "Adjust") { withAnimation { expanded.toggle() } }.buttonStyle(.borderless)
        }.padding(14).background(.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
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
            let sourceW = Double(metadata.dimensions.width ?? 1280), sourceH = Double(metadata.dimensions.height ?? 720)
            let scale = min(geo.size.width/sourceW, geo.size.height/sourceH)
            let w = CGFloat(operation.width ?? 360) * scale, h = CGFloat(operation.height ?? 360) * scale
            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 14).fill(.black.opacity(0.82)); RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.35))
                RoundedRectangle(cornerRadius: operation.shape == "circle" ? min(w,h)/2 : 14)
                    .fill(Color.accentColor.opacity(0.25))
                    .overlay { Image(systemName: operation.type.contains("masked") ? "star.fill" : "photo").foregroundStyle(.white) }
                    .frame(width: max(36,w), height: max(36,h))
                    .offset(x: CGFloat(operation.x ?? 40)*scale, y: CGFloat(operation.y ?? 40)*scale)
                    .gesture(DragGesture().onChanged { value in operation.x = Int(value.location.x/scale - w/(2*scale)); operation.y = Int(value.location.y/scale - h/(2*scale)) })
            }
            .overlay(alignment: .bottom) {
                HStack {
                    Button("Smaller") { operation.width = max(32,(operation.width ?? 360)-40); operation.height = max(32,(operation.height ?? 360)-40) }
                    Spacer(); Text("Drag to move").font(.caption).foregroundStyle(.secondary); Spacer()
                    Button("Larger") { operation.width = min(4096,(operation.width ?? 360)+40); operation.height = min(4096,(operation.height ?? 360)+40) }
                }.padding(8).background(.ultraThinMaterial)
            }
        }
    }
}

struct ServerSettings: View {
    @Environment(\.dismiss) private var dismiss
    @State private var url = UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000"
    var body: some View {
        NavigationStack {
            Form {
                Section("Backend server") {
                    TextField("https://…", text: $url).textInputAutocapitalization(.never).keyboardType(.URL)
                    Text("Use your Cloud Run HTTPS URL on a physical iPhone.").font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Save") { UserDefaults.standard.set(url, forKey: "serverURL"); dismiss() } } }
        }
    }
}
