import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/review/review_screen.dart';
import 'package:app/features/review/review_controller.dart';
import 'package:app/features/review/observation_model.dart';

class FakeReviewController extends ReviewController {
  @override
  Future<ReviewState> build(int docId) async {
    return ReviewState(
      documentId: docId,
      status: "needs_review",
      observations: [
        ObservationModel(
          id: 101,
          testName: "Hemoglobin",
          valueNum: 13.2,
          valueText: null,
          unit: "g/dL",
          refLow: 12.0,
          refHigh: 16.0,
          flag: "normal",
          collectedAt: "2026-10-01",
          pageNo: 1,
          sourceLineIds: [1, 2],
          status: "pending",
          confidence: 0.95,
        ),
      ],
      ocrLines: [],
    );
  }
}

void main() {
  testWidgets('ReviewScreen shows observation rows and Confirm all button', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          reviewControllerProvider.overrideWith(() => FakeReviewController()),
        ],
        child: const MaterialApp(home: ReviewScreen(documentId: 1)),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Hemoglobin'), findsOneWidget);
    expect(find.text('Confirm all'), findsOneWidget);
  });
}
