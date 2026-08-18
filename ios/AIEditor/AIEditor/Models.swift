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

    enum CodingKeys: String, CodingKey {
        case id, type, enabled, speed, volume, text, position, bold, layout, ratio, shape, x, y, width, height, rotation, opacity, feather, fit, loop, ducking
        case startSeconds = "start_seconds", endSeconds = "end_seconds"
        case sourceAssetId = "source_asset_id", secondaryAssetId = "secondary_asset_id"
        case fontFamily = "font_family", fontSize = "font_size", fontColor = "font_color", textBackgroundColor = "text_background_color"
        case motionKeyframes = "motion_keyframes", fadeInSeconds = "fade_in_seconds", fadeOutSeconds = "fade_out_seconds", stylePrompt = "style_prompt"
    }

    var displayTitle: String {
        switch type {
        case "trim": return "Trim"
        case "text_overlay": return "Text"
        case "split_screen": return "Split screen"
        case "picture_in_picture", "media_overlay": return "Media layer"
        case "masked_video", "masked_media": return "Shape layer"
        case "music": return "Background music"
        case "speed": return "Speed"
        case "mute": return "Mute"
        case "volume": return "Volume"
        default: return "AI change"
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
