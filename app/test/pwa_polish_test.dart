import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:app/features/documents/documents_screen.dart';
import 'package:app/features/navigation/app_router.dart';
import 'package:app/core/connectivity.dart';

void main() {
  testWidgets('documents screen shows offline message when isOfflineProvider is true', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          isOfflineProvider.overrideWithValue(true),
        ],
        child: const MaterialApp(
          home: DocumentsScreen(),
        ),
      ),
    );

    expect(find.text("You're offline"), findsOneWidget);
    expect(find.byIcon(Icons.wifi_off), findsOneWidget);
  });

  testWidgets('install hint is visible when not dismissed and disappears on dismiss', (tester) async {
    SharedPreferences.setMockInitialValues({'install_hint_dismissed': false});

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: ScaffoldWithResponsiveNav(
            child: Text('Main Content'),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.textContaining('Install SwasthyaStats'), findsOneWidget);

    await tester.tap(find.text('Dismiss'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Install SwasthyaStats'), findsNothing);
  });
}
