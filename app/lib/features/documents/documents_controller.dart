import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import 'document_model.dart';

class DocumentsController extends AsyncNotifier<List<DocumentItem>> {
  Timer? _pollingTimer;

  @override
  Future<List<DocumentItem>> build() async {
    ref.onDispose(() {
      _pollingTimer?.cancel();
    });

    final docs = await _fetchDocuments();
    _checkPolling(docs);
    return docs;
  }

  Future<List<DocumentItem>> _fetchDocuments() async {
    final client = ref.read(apiClientProvider);
    final response = await client.dio.get('/documents');
    final data = response.data as List<dynamic>;
    return data.map((d) => DocumentItem.fromJson(d as Map<String, dynamic>)).toList();
  }

  void _checkPolling(List<DocumentItem> docs) {
    _pollingTimer?.cancel();
    final hasProcessing = docs.any((d) =>
        d.status == 'queued' ||
        d.status == 'normalizing' ||
        d.status == 'ocr' ||
        d.status == 'extracting');

    if (hasProcessing) {
      _pollingTimer = Timer(const Duration(seconds: 3), () async {
        try {
          final updated = await _fetchDocuments();
          state = AsyncData(updated);
          _checkPolling(updated);
        } catch (_) {
          // Retry on next cycle
          _checkPolling(docs);
        }
      });
    }
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final docs = await _fetchDocuments();
      _checkPolling(docs);
      return docs;
    });
  }

  Future<void> uploadFiles(List<MultipartFile> files) async {
    final client = ref.read(apiClientProvider);
    final formData = FormData();
    for (final file in files) {
      formData.files.add(MapEntry('files', file));
    }

    await client.dio.post(
      '/documents',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    await refresh();
  }
}

final documentsControllerProvider =
    AsyncNotifierProvider<DocumentsController, List<DocumentItem>>(() {
  return DocumentsController();
});
