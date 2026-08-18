import CoreTransferable
import Foundation
import PhotosUI
import UniformTypeIdentifiers
import UIKit
import SwiftUI

struct PickedMovie: Transferable {
    let url: URL
    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { movie in
            SentTransferredFile(movie.url)
        } importing: { received in
            let destination = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID().uuidString).mov")
            try? FileManager.default.removeItem(at: destination)
            try FileManager.default.copyItem(at: received.file, to: destination)
            return PickedMovie(url: destination)
        }
    }
}

enum MediaImport {
    static func prepare(_ item: PhotosPickerItem) async throws -> ImportedMedia {
        if item.supportedContentTypes.contains(where: { $0.conforms(to: .movie) }) {
            guard let movie = try await item.loadTransferable(type: PickedMovie.self) else { throw importError }
            return ImportedMedia(url: movie.url, filename: "video-\(UUID().uuidString).mov", mimeType: "video/quicktime", kind: "video")
        }
        guard let data = try await item.loadTransferable(type: Data.self), let image = UIImage(data: data), let jpeg = image.jpegData(compressionQuality: 0.9) else { throw importError }
        let destination = FileManager.default.temporaryDirectory.appendingPathComponent("photo-\(UUID().uuidString).jpg")
        try jpeg.write(to: destination, options: .atomic)
        return ImportedMedia(url: destination, filename: destination.lastPathComponent, mimeType: "image/jpeg", kind: "image")
    }

    static func prepareAudio(_ url: URL) throws -> ImportedMedia {
        let access = url.startAccessingSecurityScopedResource(); defer { if access { url.stopAccessingSecurityScopedResource() } }
        let ext = url.pathExtension.isEmpty ? "m4a" : url.pathExtension
        let destination = FileManager.default.temporaryDirectory.appendingPathComponent("audio-\(UUID().uuidString).\(ext)")
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.copyItem(at: url, to: destination)
        return ImportedMedia(url: destination, filename: url.lastPathComponent, mimeType: "audio/*", kind: "audio")
    }

    private static var importError: NSError { NSError(domain: "AIEditor", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not import this media item."]) }
}
