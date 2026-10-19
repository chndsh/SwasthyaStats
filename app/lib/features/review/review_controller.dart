import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/core/api_client.dart';
import 'package:app/features/review/observation_model.dart';

class ReviewState {
  final int documentId;
  final String status;
  final List<ObservationModel> observations;
  final List<dynamic> ocrLines;
  final int pageCount;
  final int selectedPageNo;
  final int? selectedObservationId;
  final bool isConfirming;

  ReviewState({
    required this.documentId,
    required this.status,
    required this.observations,
    required this.ocrLines,
    this.pageCount = 1,
    this.selectedPageNo = 1,
    this.selectedObservationId,
    this.isConfirming = false,
  });

  ReviewState copyWith({
    String? status,
    List<ObservationModel>? observations,
    List<dynamic>? ocrLines,
    int? pageCount,
    int? selectedPageNo,
    int? selectedObservationId,
    bool? isConfirming,
  }) {
    return ReviewState(
      documentId: documentId,
      status: status ?? this.status,
      observations: observations ?? this.observations,
      ocrLines: ocrLines ?? this.ocrLines,
      pageCount: pageCount ?? this.pageCount,
      selectedPageNo: selectedPageNo ?? this.selectedPageNo,
      selectedObservationId: selectedObservationId ?? this.selectedObservationId,
      isConfirming: isConfirming ?? this.isConfirming,
    );
  }
}

class ReviewController extends FamilyAsyncNotifier<ReviewState, int> {
  final int initialDocId;

  ReviewController([this.initialDocId = 0]);

  @override
  Future<ReviewState> build(int docId) async {
    final client = ref.read(apiClientProvider);
    final response = await client.dio.get('/documents/$docId/extraction');
    final data = response.data as Map<String, dynamic>;

    final rawList = data['observations'] as List<dynamic>? ?? [];
    final obs = rawList
        .map((e) => ObservationModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // Sort observations: lowest confidence first to prioritize human review
    obs.sort((a, b) {
      final confA = a.confidence ?? 1.0;
      final confB = b.confidence ?? 1.0;
      return confA.compareTo(confB);
    });

    final firstPage = obs.isNotEmpty ? obs.first.pageNo : 1;
    final firstObsId = obs.isNotEmpty ? obs.first.id : null;

    return ReviewState(
      documentId: docId,
      status: data['status'] as String? ?? 'needs_review',
      observations: obs,
      ocrLines: data['ocr_lines'] as List<dynamic>? ?? [],
      pageCount: data['page_count'] as int? ?? 1,
      selectedPageNo: firstPage,
      selectedObservationId: firstObsId,
    );
  }

  void selectObservation(ObservationModel obs) {
    state = state.whenData((s) => s.copyWith(
          selectedObservationId: obs.id,
          selectedPageNo: obs.pageNo,
        ));
  }

  void selectPage(int pageNo) {
    state = state.whenData((s) => s.copyWith(selectedPageNo: pageNo));
  }

  Future<void> updateObservation(int obsId, Map<String, dynamic> patch) async {
    final client = ref.read(apiClientProvider);
    final response = await client.dio.patch('/observations/$obsId', data: patch);
    final updated = ObservationModel.fromJson(response.data as Map<String, dynamic>);

    state = state.whenData((s) {
      final newObs = s.observations.map((o) => o.id == obsId ? updated : o).toList();
      return s.copyWith(observations: newObs);
    });
  }

  Future<bool> confirmAll() async {
    final client = ref.read(apiClientProvider);
    final current = state.value;
    if (current == null) return false;

    state = state.whenData((s) => s.copyWith(isConfirming: true));
    try {
      await client.dio.post('/documents/${current.documentId}/confirm');
      state = state.whenData((s) => s.copyWith(
            status: 'confirmed',
            isConfirming: false,
          ));
      return true;
    } catch (e) {
      state = state.whenData((s) => s.copyWith(isConfirming: false));
      return false;
    }
  }
}

final reviewControllerProvider =
    AsyncNotifierProvider.family<ReviewController, ReviewState, int>(
  () => ReviewController(),
);
