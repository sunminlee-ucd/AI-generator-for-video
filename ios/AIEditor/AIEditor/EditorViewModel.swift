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
        Task { await perform("Uploading") {
            let media = try await MediaImport.prepare(item)
            let project = try await APIClient.shared.createProject(media)
            self.project = project
            self.draftOperations = project.operations
            self.messages = [ChatMessage(role: "assistant", text: "Your \(project.sourceKind) is ready. Tell me what you want to change.")]
        }}
    }

    func add(from item: PhotosPickerItem) {
        guard let id = project?.id else { return }
        Task { await perform("Adding media") {
            let media = try await MediaImport.prepare(item)
            _ = try await APIClient.shared.addAsset(projectID: id, media: media)
            self.project = try await APIClient.shared.getProject(id)
        }}
    }

    func addAudio(_ url: URL) {
        guard let id = project?.id else { return }
        Task { await perform("Adding music") {
            let media = try MediaImport.prepareAudio(url)
            _ = try await APIClient.shared.addAsset(projectID: id, media: media)
            self.project = try await APIClient.shared.getProject(id)
        }}
    }

    func ask(_ prompt: String) {
        guard let id = project?.id, !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
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
        guard let id = project?.id, let proposal else { return }
        let existing = project?.operations.count ?? 0
        let proposed = Array(draftOperations.dropFirst(existing))
        Task { await perform("Rendering") {
            let start = try await APIClient.shared.apply(projectID: id, prompt: self.proposalPrompt, message: proposal.assistantMessage, operations: proposed)
            try await self.waitForJob(start.jobId)
            self.project = try await APIClient.shared.getProject(id)
            self.draftOperations = self.project?.operations ?? []
            self.proposal = nil
        }}
    }

    func renderChanges() {
        guard let id = project?.id, proposal == nil else { return }
        Task { await perform("Rendering") {
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

    private func waitForJob(_ id: String) async throws {
        while true {
            let job = try await APIClient.shared.job(id)
            if job.status == "completed" { return }
            if job.status == "failed" { throw NSError(domain: "AIEditor", code: 2, userInfo: [NSLocalizedDescriptionKey: job.error ?? "Rendering failed"]) }
            try await Task.sleep(for: .milliseconds(850))
        }
    }

    private func perform(_ working: String, _ work: @escaping () async throws -> Void) async {
        busy = true; status = working; errorMessage = nil
        do { try await work(); status = "Ready" } catch { errorMessage = error.localizedDescription; status = "Failed" }
        busy = false
    }
}
