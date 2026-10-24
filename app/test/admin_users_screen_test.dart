import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/core/api_client.dart';
import 'package:app/features/admin/admin_users_controller.dart';
import 'package:app/features/admin/admin_users_screen.dart';

class _FakeApiClient extends Fake implements ApiClient {}

void main() {
  testWidgets('admin users screen provides back navigation', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          adminUsersControllerProvider.overrideWith(
            (ref) => AdminUsersController(_FakeApiClient()),
          ),
        ],
        child: MaterialApp(
          home: Navigator(
            onGenerateRoute: (_) => MaterialPageRoute(
              settings: const RouteSettings(name: '/admin/users'),
              builder: (_) => const AdminUsersScreen(),
            ),
          ),
        ),
      ),
    );

    await tester.pump();

    expect(find.byType(BackButton), findsOneWidget);
  });
}
