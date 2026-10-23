import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/documents/documents_screen.dart';
import 'package:app/features/documents/documents_controller.dart';
import 'package:app/features/documents/document_model.dart';

class FakeDocumentsController extends DocumentsController {
  @override
  Future<List<DocumentItem>> build() async {
    return [
      DocumentItem(
        id: 1,
        filename: "cbc_report.pdf",
        status: "needs_review",
        pageCount: 2,
        createdAt: DateTime.now(),
      ),
      DocumentItem(
        id: 2,
        filename: "lipid_panel.png",
        status: "ocr",
        pageCount: 1,
        createdAt: DateTime.now(),
      ),
      DocumentItem(
        id: 3,
        filename: "urine_analysis.pdf",
        status: "rate_limited",
        pageCount: 1,
        createdAt: DateTime.now(),
      ),
    ];
  }
}

void main() {
  test('DocumentItem parses doctorName from JSON', () {
    final doc = DocumentItem.fromJson({
      'id': 1,
      'filename': 'report.pdf',
      'status': 'confirmed',
      'doctor_name': 'Dr. Sharma',
      'created_at': '2026-10-23T00:00:00Z',
      'page_count': 1,
      'patient_id': 1,
    });
    expect(doc.doctorName, 'Dr. Sharma');
  });

  testWidgets('DocumentsScreen displays documents and status chips', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentsControllerProvider.overrideWith(() => FakeDocumentsController()),
        ],
        child: const MaterialApp(home: DocumentsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('cbc_report.pdf'), findsOneWidget);
    expect(find.text('needs_review'), findsOneWidget);
    expect(find.text('lipid_panel.png'), findsOneWidget);
    expect(find.byIcon(Icons.add), findsOneWidget);
  });

  testWidgets('DocumentsScreen displays rate_limited chip', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentsControllerProvider.overrideWith(() => FakeDocumentsController()),
        ],
        child: const MaterialApp(home: DocumentsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Rate limited (tap to retry)'), findsOneWidget);
  });
}
