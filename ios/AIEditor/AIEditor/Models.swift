import Foundation

struct Dimensions: Codable { let width: Int?; let height: Int? }
struct MediaMetadata: Codable {
    let kind: String?
    let durationSeconds: Double
    let dimensions: Dimensions
    let hasVideo: Bool
    let hasAudio: Bool
    enum CodingKeys: String, CodingKey {
        case kind, dimensions
        case durationSeconds = "duration_seconds"
        case hasVideo = "has_video"
        case hasAudio = "has_audio"
    }
}

struct MediaAsset: Codable, Identifiable {
    let id: String
    let filename: String
    let kind: String
    let metadata: MediaMetadata
    let url: String
}

struct MotionKeyframe: Codable, Identifiable {
    var id: String { "\(timeSeconds)-\(x)-\(y)" }
    var timeSeconds: Double
    var x: Int
    var y: Int
    var easing: String
    enum CodingKeys: String, CodingKey {
        case x, y, easing
        case timeSeconds = "time_seconds"
    }
}

struct EditOperation: Codable, Identifiable {
    var id: String
    var type: String
    var enabled: Bool = true
    var startSeconds: Double?
    var endSeconds: Double?
    var sourceAssetId: String?
    var secondaryAssetId: String?
    var tertiaryAssetId: String?
    var speed: Double?
    var volume: Double?
    var text: String?
    var position: String?
    var fontFamily: String?
    var fontSize: Int?
    var fontColor: String?
    var textBackgroundColor: String?
    var bold: Bool?
    var layout: String?
    var ratio: Double?
    var shape: String?
    var x: Int?
    var y: Int?
    var width: Int?
    var height: Int?
    var rotation: Double?
    var opacity: Double?
    var feather: Int?
    var fit: String?
    var motionKeyframes: [MotionKeyframe]?
    var fadeInSeconds: Double?
    var fadeOutSeconds: Double?
    var loop: Bool?
    var ducking: Bool?
    var stylePrompt: String?
    var turnDurationSeconds: Double?
    var turnDirection: String?
    var removeBackground: Bool?

    init(
        id: String = UUID().uuidString.replacingOccurrences(of: "-", with: ""),
        type: String,
        enabled: Bool = true,
        startSeconds: Double? = nil,
        endSeconds: Double? = nil,
        sourceAssetId: String? = nil,
        secondaryAssetId: String? = nil,
        tertiaryAssetId: String? = nil,
        speed: Double? = nil,
        volume: Double? = nil,
        text: String? = nil,
        position: String? = nil,
        fontFamily: String? = "DejaVu Sans",
        fontSize: Int? = 48,
        fontColor: String? = "white",
        textBackgroundColor: String? = "black@0.45",
        bold: Bool? = false,
        layout: String? = nil,
        ratio: Double? = 0.5,
        shape: String? = nil,
        x: Int? = 40,
        y: Int? = 40,
        width: Int? = 360,
        height: Int? = 360,
        rotation: Double? = 0,
        opacity: Double? = 1,
        feather: Int? = 0,
        fit: String? = nil,
        motionKeyframes: [MotionKeyframe]? = [],
        fadeInSeconds: Double? = 0,
        fadeOutSeconds: Double? = 0,
        loop: Bool? = true,
        ducking: Bool? = false,
        stylePrompt: String? = nil,
        turnDurationSeconds: Double? = 4,
        turnDirection: String? = "left",
        removeBackground: Bool? = true
    ) {
        self.id = id
        self.type = type
        self.enabled = enabled
        self.startSeconds = startSeconds
        self.endSeconds = endSeconds
        self.sourceAssetId = sourceAssetId
        self.secondaryAssetId = secondaryAssetId
        self.tertiaryAssetId = tertiaryAssetId
        self.speed = speed
        self.volume = volume
        self.text = text
        self.position = position
        self.fontFamily = fontFamily
        self.fontSize = fontSize
        self.fontColor = fontColor
        self.textBackgroundColor = textBackgroundColor
        self.bold = bold
        self.layout = layout
        self.ratio = ratio
        self.shape = shape
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.rotation = rotation
        self.opacity = opacity
        self.feather = feather
        self.fit = fit
        self.motionKeyframes = motionKeyframes
        self.fadeInSeconds = fadeInSeconds
        self.fadeOutSeconds = fadeOutSeconds
        self.loop = loop
        self.ducking = ducking
        self.stylePrompt = stylePrompt
        self.turnDurationSeconds = turnDurationSeconds
        self.turnDirection = turnDirection
        self.removeBackground = removeBackground
    }

    enum CodingKeys: String, CodingKey {
        case id, type, enabled, speed, volume, text, position, bold, layout, ratio, shape, x, y, width, height, rotation, opacity, feather, fit, loop, ducking
        case startSeconds = "start_seconds", endSeconds = "end_seconds"
        case sourceAssetId = "source_asset_id", secondaryAssetId = "secondary_asset_id", tertiaryAssetId = "tertiary_asset_id"
        case fontFamily = "font_family", fontSize = "font_size", fontColor = "font_color", textBackgroundColor = "text_background_color"
        case motionKeyframes = "motion_keyframes", fadeInSeconds = "fade_in_seconds", fadeOutSeconds = "fade_out_seconds", stylePrompt = "style_prompt"
        case turnDurationSeconds = "turn_duration_seconds", turnDirection = "turn_direction", removeBackground = "remove_background"
    }

    var displayTitle: String {
        switch type {
        case "trim": return "Trim"
        case "text_overlay": return "Text"
        case "split_screen": return "Split screen"
        case "picture_in_picture": return "Picture in picture"
        case "media_overlay": return "Media layer"
        case "masked_video", "masked_media": return "Shape layer"
        case "concat": return "Join clips"
        case "music": return "Background music"
        case "speed": return "Speed"
        case "mute": return "Mute"
        case "volume": return "Volume"
        case "style_transfer": return "Visual style"
        case "photo_turn_3d": return "Photo 3D Turn"
        default: return "Edit"
        }
    }
}

struct Project: Codable, Identifiable {
    let id: String
    let filename: String
    let sourceKind: String
    let metadata: MediaMetadata
    var operations: [EditOperation]
    var assets: [MediaAsset]
    let sourceUrl: String
    let previewUrl: String?
    enum CodingKeys: String, CodingKey {
        case id, filename, metadata, operations, assets
        case sourceKind = "source_kind", sourceUrl = "source_url", previewUrl = "preview_url"
    }
}

struct EditPlan: Codable { let assistantMessage: String; var operations: [EditOperation]; enum CodingKeys: String, CodingKey { case assistantMessage = "assistant_message", operations } }
struct ProposalResponse: Codable { let status: String; let assistantMessage: String; let plan: EditPlan; enum CodingKeys: String, CodingKey { case status, plan; case assistantMessage = "assistant_message" } }
struct JobStart: Codable { let jobId: String; let status: String; enum CodingKeys: String, CodingKey { case status; case jobId = "job_id" } }
struct Job: Codable { let status: String; let error: String?; let outputUrl: String?; enum CodingKeys: String, CodingKey { case status, error; case outputUrl = "output_url" } }

struct ImportedMedia { let url: URL; let filename: String; let mimeType: String; let kind: String }
