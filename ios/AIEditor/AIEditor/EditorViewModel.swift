import Foundation
import PhotosUI
import SwiftUI

struct ChatMessage: Identifiable { let id = UUID(); let role: String; let text: String }

@MainActor
final class EditorViewModel: ObservableObject {
    @Published var project: Project?
    @Published var proposal: EditPlan?
    @Published var proposalPrompt = ""
    @Published var draftOperations: [EditOperation] = []
    @Published var messages: [ChatMessage] = []
    @Published var busy = false
    @Published var status = "Ready"
    @Published var selectedTab = 0
    @Published var errorMessage: String?

    func create(from item: PhotosPickerItem) {
        guard !busy else { return }
        Task { await perform("Uploading") {
            let media = try await MediaImport.prepare(item)
            let project = try await APIClient.shared.createProject(media)
            self.project = project
            self.draftOperations = project.operations
            self.proposal = nil
            self.messages = [ChatMessage(role: "assistant", text: "Your \(project.sourceKind) is ready. Use Quick tools or tell me what you want to change.")]
        }}
    }

    func add(from item: PhotosPickerItem) {
        guard let id = project?.id, !busy else { return }
        Task { await perform("Adding media") {
            let media = try await MediaImport.prepare(item)
            _ = try await APIClient.shared.addAsset(projectID: id, media: media)
            self.project = try await APIClient.shared.getProject(id)
        }}
    }

    func addAudio(_ url: URL) {
        guard let id = project?.id, !busy else { return }
        Task { await perform("Adding music") {
            let media = try MediaImport.prepareAudio(url)
            _ = try await APIClient.shared.addAsset(projectID: id, media: media)
            self.project = try await APIClient.shared.getProject(id)
        }}
    }

    func addManualOperation(_ operation: EditOperation) {
        guard !busy else { return }
        proposal = nil
        proposalPrompt = ""
        draftOperations.append(operation)
        status = "Edit added"
    }

    func removeOperation(at index: Int) {
        guard draftOperations.indices.contains(index), !busy else { return }
        proposal = nil
        proposalPrompt = ""
        draftOperations.remove(at: index)
        status = "Edit removed"
    }

    func ask(_ prompt: String) {
        guard let id = project?.id, !busy, !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        messages.append(ChatMessage(role: "user", text: prompt))
        Task { await perform("AI is planning") {
            let result = try await APIClient.shared.propose(projectID: id, prompt: prompt)
            self.proposal = result.plan
            self.proposalPrompt = prompt
            self.draftOperations = (self.project?.operations ?? []) + result.plan.operations
            self.messages.append(ChatMessage(role: "assistant", text: result.assistantMessage))
            self.selectedTab = 1
        }}
    }

    func applyProposal() {
        guard let id = project?.id, let proposal, !busy else { return }
        let existing = project?.operations.count ?? 0
        let proposed = Array(draftOperations.dropFirst(existing))
        Task { await perform("Rendering") {
            try self.validateDraftOperations()
            let start = try await APIClient.shared.apply(projectID: id, prompt: self.proposalPrompt, message: proposal.assistantMessage, operations: proposed)
            try await self.waitForJob(start.jobId)
            self.project = try await APIClient.shared.getProject(id)
            self.draftOperations = self.project?.operations ?? []
            self.proposal = nil
        }}
    }

    func renderChanges() {
        guard let id = project?.id, proposal == nil, !busy else { return }
        Task { await perform("Rendering") {
            try self.validateDraftOperations()
            let start = try await APIClient.shared.replace(projectID: id, operations: self.draftOperations)
            try await self.waitForJob(start.jobId)
            self.project = try await APIClient.shared.getProject(id)
            self.draftOperations = self.project?.operations ?? []
        }}
    }

    func absolute(_ path: String?) async -> URL? {
        guard let path else { return nil }
        return await APIClient.shared.absolute(path)
    }

    private func validateDraftOperations() throws {
        guard let project else { return }
        let visualIds = Set(project.assets.filter { $0.kind == "image" || $0.kind == "video" }.map(\.id))
        let videoIds = Set(project.assets.filter { $0.kind == "video" }.map(\.id))
        let audioIds = Set(project.assets.filter { $0.kind == "audio" }.map(\.id))
        let duration = project.metadata.durationSeconds

        for operation in draftOperations where operation.enabled {
            switch operation.type {
            case "trim":
                let start = operation.startSeconds ?? 0
                let end = operation.endSeconds ?? duration
                if start < 0 || end <= start || end > duration + 0.05 { throw validationError("Trim range must stay inside the clip duration.") }
            case "split_screen", "picture_in_picture":
                if !visualIds.contains(operation.secondaryAssetId ?? "") { throw validationError("Choose a photo or video for \(operation.displayTitle).") }
            case "concat":
                if !videoIds.contains(operation.secondaryAssetId ?? "") { throw validationError("Join clips needs a second video.") }
            case "media_overlay", "masked_media":
                if !visualIds.contains(operation.sourceAssetId ?? "") { throw validationError("Choose a photo or video for \(operation.displayTitle).") }
            case "music":
                if !audioIds.contains(operation.sourceAssetId ?? "") { throw validationError("Background music needs an audio file.") }
            case "text_overlay":
                if (operation.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { throw validationError("Text cannot be empty.") }
            case "style_transfer":
                if (operation.stylePrompt ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { throw validationError("Describe the visual style first.") }
            default:
                break
            }
        }
    }

    private func validationError(_ message: String) -> NSError {
        NSError(domain: "AIEditor", code: 3, userInfo: [NSLocalizedDescriptionKey: message])
    }

    private func waitForJob(_ id: String) async throws {
        let deadline = Date().addingTimeInterval(600)
        while true {
            let job = try await APIClient.shared.job(id)
            if job.status == "completed" { return }
            if job.status == "failed" { throw NSError(domain: "AIEditor", code: 2, userInfo: [NSLocalizedDescriptionKey: job.error ?? "Rendering failed"]) }
            if Date() > deadline { throw NSError(domain: "AIEditor", code: 4, userInfo: [NSLocalizedDescriptionKey: "Rendering timed out. Try a shorter clip or fewer layers."]) }
            try await Task.sleep(for: .milliseconds(850))
        }
    }

    private func perform(_ working: String, _ work: @escaping () async throws -> Void) async {
        busy = true
        status = working
        errorMessage = nil
        do {
            try await work()
            status = "Ready"
        } catch {
            errorMessage = error.localizedDescription
            status = "Failed"
        }
        busy = false
    }
}
