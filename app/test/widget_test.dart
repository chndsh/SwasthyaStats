import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/main.dart';
import 'package:app/features/settings/settings_controller.dart';
import 'package:app/features/settings/settings_model.dart';
import 'package:app/core/api_client.dart';

void main() {
  testWidgets('App shell loads without errors smoke test', (WidgetTester tester) async {
    final mockSettings = AppSettings(
      llmProvider: 'groq',
      llmBaseUrl: 'https://api.groq.com/openai/v1',
      llmApiKeys: [],
      llmKeyStrategy: 'failover',
      llmModel: 'llama-3.3-70b-versatile',
      llmStructuredMode: 'auto',
      llmSupportsTools: true,
      llmDailyTokenCap: 200000,
      privacyRedactPii: true,
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          settingsControllerProvider.overrideWith(
            (ref) => SettingsControllerMock(mockSettings),
          ),
        ],
        child: const SwasthyaStatsApp(),
      ),
    );

    await tester.pump();
    expect(find.byType(SwasthyaStatsApp), findsOneWidget);
  });
}

class SettingsControllerMock extends SettingsController {
  SettingsControllerMock(AppSettings settings)
      : super(FakeApiClient()) {
    state = SettingsState(
      settings: AsyncValue.data(settings),
      models: const AsyncValue.data(['llama-3.3-70b-versatile']),
      usage: const AsyncValue.data(null),
      testResult: const AsyncValue.data(null),
    );
  }

  @override
  Future<void> loadAll() async {}
}

class FakeApiClient extends Fake implements ApiClient {
}
