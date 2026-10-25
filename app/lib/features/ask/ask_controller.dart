import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/local_cache.dart';
import '../auth/auth_controller.dart';
import 'ask_model.dart';

final askControllerProvider =
    StateNotifierProvider<AskController, AsyncValue<List<AskMessage>>>(
  (ref) {
    final authState = ref.watch(authControllerProvider);
    final client = ref.watch(apiClientProvider);
    final cache = ref.watch(localCacheServiceProvider);
    if (!authState.isAuthenticated) {
      return AskController(client, null);
    }
    return AskController(client, cache);
  },
);

class AskController extends StateNotifier<AsyncValue<List<AskMessage>>> {
  final ApiClient _client;
  final LocalCacheService? _cache;

  AskController(this._client, [this._cache]) : super(const AsyncValue.data([])) {
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    if (_cache != null) {
      final cached = await _cache.getCachedAskHistory();
      if (cached.isNotEmpty) {
        final msgs = cached.map((m) => AskMessage.fromJson(m)).toList();
        state = AsyncValue.data(msgs);
      }
    }
  }

  Future<void> sendQuestion(String question) async {
    final q = question.trim();
    if (q.isEmpty) return;

    final currentMessages = state.value ?? [];
    final userMsg = AskMessage(role: 'user', text: q);

    final updatedWithUser = [...currentMessages, userMsg];
    state = AsyncValue.data(updatedWithUser);

    try {
      final response = await _client.dio.post(
        '/ask',
        data: {'question': q},
      );

      final data = response.data as Map<String, dynamic>;
      final answer = data['answer'] as String? ?? 'No response received.';
      final rawCitations = (data['citations'] as List<dynamic>?) ?? [];
      final citations = rawCitations
          .map((c) => CitationRef.fromJson(c as Map<String, dynamic>))
          .toList();

      final assistantMsg = AskMessage(
        role: 'assistant',
        text: answer,
        citations: citations,
      );

      final currentList = state.value ?? <AskMessage>[];
      final finalMessages = <AskMessage>[...currentList, assistantMsg];
      state = AsyncValue.data(finalMessages);

      if (_cache != null) {
        await _cache.cacheAskHistory(finalMessages.map((m) => m.toJson()).toList());
      }
    } catch (e) {
      final errorMsg = AskMessage(
        role: 'assistant',
        text: 'Error asking question: $e',
      );
      final currentList = state.value ?? <AskMessage>[];
      state = AsyncValue.data(<AskMessage>[...currentList, errorMsg]);
    }
  }

  Future<void> clearHistory() async {
    state = const AsyncValue.data([]);
    if (_cache != null) {
      await _cache.clearAskHistory();
    }
  }
}
