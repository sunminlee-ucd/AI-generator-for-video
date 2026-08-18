import Foundation

actor APIClient {
    static let shared = APIClient()
    private let defaultServer = "https://ai-generator-for-video-git-279005246322.europe-west2.run.app"

    var baseURL: URL {
        let saved = UserDefaults.standard.string(forKey: "serverURL")?.trimmingCharacters(in: .whitespacesAndNewlines)
        let effective: String
        if saved == nil || saved?.isEmpty == true || saved == "http://localhost:8000" || saved == "http://10.0.2.2:8000" {
            effective = defaultServer
        } else {
            effective = saved!
        }
        return URL(string: effective.trimmingCharacters(in: CharacterSet(charactersIn: "/")))!
    }

    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    func createProject(_ media: ImportedMedia, stillDuration: Double = 5) async throws -> Project {
        let data = try Data(contentsOf: media.url)
        let response = try await multipart(path: "/api/projects", data: data, filename: media.filename, mime: media.mimeType, fields: ["still_duration_seconds": "\(stillDuration)"])
        return try decoder.decode(Project.self, from: response)
    }

    func addAsset(projectID: String, media: ImportedMedia) async throws -> MediaAsset {
        let data = try Data(contentsOf: media.url)
        let response = try await multipart(path: "/api/projects/\(projectID)/assets", data: data, filename: media.filename, mime: media.mimeType, fields: ["kind": media.kind])
        return try decoder.decode(MediaAsset.self, from: response)
    }

    func getProject(_ id: String) async throws -> Project { try await get("/api/projects/\(id)", as: Project.self) }

    func propose(projectID: String, prompt: String) async throws -> ProposalResponse {
        try await json(path: "/api/projects/\(projectID)/commands", method: "POST", body: ["prompt": prompt], as: ProposalResponse.self)
    }

    func apply(projectID: String, prompt: String, message: String, operations: [EditOperation]) async throws -> JobStart {
        struct Body: Encodable { let prompt: String; let assistant_message: String; let operations: [EditOperation] }
        return try await jsonEncodable(path: "/api/projects/\(projectID)/apply-plan", method: "POST", body: Body(prompt: prompt, assistant_message: message, operations: operations), as: JobStart.self)
    }

    func replace(projectID: String, operations: [EditOperation]) async throws -> JobStart {
        struct Body: Encodable { let operations: [EditOperation] }
        return try await jsonEncodable(path: "/api/projects/\(projectID)/operations", method: "PUT", body: Body(operations: operations), as: JobStart.self)
    }

    func job(_ id: String) async throws -> Job { try await get("/api/jobs/\(id)", as: Job.self) }
    func absolute(_ path: String) -> URL { path.hasPrefix("http") ? URL(string: path)! : baseURL.appending(path: path) }

    private func get<T: Decodable>(_ path: String, as: T.Type) async throws -> T {
        let (data, response) = try await URLSession.shared.data(from: absolute(path)); try validate(response, data); return try decoder.decode(T.self, from: data)
    }

    private func json<T: Decodable>(path: String, method: String, body: [String: String], as: T.Type) async throws -> T {
        var request = URLRequest(url: absolute(path)); request.httpMethod = method; request.setValue("application/json", forHTTPHeaderField: "Content-Type"); request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request); try validate(response, data); return try decoder.decode(T.self, from: data)
    }

    private func jsonEncodable<B: Encodable, T: Decodable>(path: String, method: String, body: B, as: T.Type) async throws -> T {
        var request = URLRequest(url: absolute(path)); request.httpMethod = method; request.setValue("application/json", forHTTPHeaderField: "Content-Type"); request.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: request); try validate(response, data); return try decoder.decode(T.self, from: data)
    }

    private func multipart(path: String, data: Data, filename: String, mime: String, fields: [String: String]) async throws -> Data {
        let boundary = "Boundary-\(UUID().uuidString)"; var body = Data()
        for (key, value) in fields { body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(key)\"\r\n\r\n\(value)\r\n".data(using: .utf8)!) }
        body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\nContent-Type: \(mime)\r\n\r\n".data(using: .utf8)!); body.append(data); body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        var request = URLRequest(url: absolute(path)); request.httpMethod = "POST"; request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type"); request.httpBody = body
        let (result, response) = try await URLSession.shared.data(for: request); try validate(response, result); return result
    }

    private func validate(_ response: URLResponse, _ data: Data) throws {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String ?? "Server request failed"
            throw NSError(domain: "AIEditor", code: (response as? HTTPURLResponse)?.statusCode ?? -1, userInfo: [NSLocalizedDescriptionKey: message])
        }
    }
}

private extension URL {
    func appending(path: String) -> URL { URL(string: path.hasPrefix("/") ? String(absoluteString.dropLast(absoluteString.hasSuffix("/") ? 1 : 0)) + path : absoluteString + "/" + path)! }
}
