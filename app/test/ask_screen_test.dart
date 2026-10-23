import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/ask/ask_screen.dart';
import 'package:app/features/ask/ask_model.dart';
import 'package:app/features/ask/ask_controller.dart';
import 'package:app/core/api_client.dart';


class FakeAskController extends AskController {
  FakeAskController(super.client);

  @override
  Future<void> sendQuestion(String question) async {
    final current = state.value ?? [];
    state = AsyncValue.data([
      ...current,
      AskMessage(role: 'user', text: question),
      AskMessage(
        role: 'assistant',
        text: 'Your HbA1c is 7.2% [obs:101].',
        citations: [CitationRef(type: 'obs', id: 101)],
      ),
    ]);
  }
}

void main() {
  testWidgets('ask screen renders text field and send button', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: AskScreen(),
        ),
      ),
    );

    expect(find.byType(TextField), findsOneWidget);
    expect(find.byIcon(Icons.send), findsOneWidget);
    expect(find.text('Ask anything about your health records'), findsOneWidget);
    expect(find.text('What was my last HbA1c?'), findsOneWidget);
    expect(find.text('Are any results abnormal?'), findsOneWidget);
  });

  testWidgets('submitting question shows user message and assistant reply with citation chip', (tester) async {
    final fakeController = FakeAskController(ApiClient());

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          askControllerProvider.overrideWith((ref) => fakeController),
        ],
        child: const MaterialApp(
          home: AskScreen(),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), 'What is my HbA1c?');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    expect(find.text('What is my HbA1c?'), findsOneWidget);
    expect(find.text('obs:101'), findsOneWidget);
  });
}
