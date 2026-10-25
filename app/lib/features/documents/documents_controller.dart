import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/local_cache.dart';
import '../auth/auth_controller.dart';
import 'document_model.dart';

class DocumentsController extends AsyncNotifier<List<DocumentItem>> {
  Timer? _pollingTimer;

  @override
  Future<List<DocumentItem>> build() async {
    ref.onDispose(() {
      _pollingTimer?.cancel();
    });

    final authState = ref.watch(authControllerProvider);
    if (!authState.isAuthenticated) {
      _pollingTimer?.cancel();
      return [];
    }
    ref.watch(localCacheServiceProvider);

    final docs = await _fetchDocuments();
    _checkPolling(docs);
    return docs;
  }

  Future<List<DocumentItem>> _fetchDocuments() async {
    final client = ref.read(apiClientProvider);
    final cache = ref.read(localCacheServiceProvider);
    try {
      final response = await client.dio.get('/documents');
      final data = response.data as List<dynamic>;
      final rawMaps = data.map((d) => d as Map<String, dynamic>).toList();
      await cache?.cacheDocuments(rawMaps);
      return rawMaps.map((d) => DocumentItem.fromJson(d)).toList();
    } catch (_) {
      final cached = await cache?.getCachedDocuments() ?? [];
      if (cached.isNotEmpty) {
        return cached.map((d) => DocumentItem.fromJson(d)).toList();
      }
      rethrow;
    }
  }

  void _checkPolling(List<DocumentItem> docs) {
    _pollingTimer?.cancel();
    final hasProcessing = docs.any((d) =>
        d.status == 'queued' ||
        d.status == 'normalizing' ||
        d.status == 'ocr' ||
        d.status == 'extracting');

    final pollInterval = hasProcessing ? const Duration(seconds: 3) : const Duration(seconds: 10);
    _pollingTimer = Timer(pollInterval, () async {
      try {
        final updated = await _fetchDocuments();
        state = AsyncData(updated);
        _checkPolling(updated);
      } catch (_) {
        _checkPolling(docs);
      }
    });
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

  Future<void> deleteDocuments(Set<int> ids) async {
    final client = ref.read(apiClientProvider);
    await Future.wait(ids.map((id) => client.dio.delete('/documents/$id')));
    await refresh();
  }
}

final documentsControllerProvider =
    AsyncNotifierProvider<DocumentsController, List<DocumentItem>>(() {
  return DocumentsController();
});
