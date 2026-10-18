import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import 'ask_model.dart';

final askControllerProvider =
    StateNotifierProvider<AskController, AsyncValue<List<AskMessage>>>(
  (ref) {
    final client = ref.watch(apiClientProvider);
    return AskController(client);
  },
);

class AskController extends StateNotifier<AsyncValue<List<AskMessage>>> {
  final ApiClient _client;

  AskController(this._client) : super(const AsyncValue.data([]));

  Future<void> sendQuestion(String question) async {
    final q = question.trim();
    if (q.isEmpty) return;

    final currentMessages = state.value ?? [];
    final userMsg = AskMessage(role: 'user', text: q);

    state = AsyncValue.data([...currentMessages, userMsg]);

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

      state = AsyncValue.data([...state.value ?? [], assistantMsg]);
    } catch (e) {
      final errorMsg = AskMessage(
        role: 'assistant',
        text: 'Error asking question: $e',
      );
      state = AsyncValue.data([...state.value ?? [], errorMsg]);
    }
  }

  void clearHistory() {
    state = const AsyncValue.data([]);
  }
}
