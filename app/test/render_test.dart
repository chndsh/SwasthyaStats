import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/navigation/app_router.dart';
import 'package:app/features/auth/auth_controller.dart';
import 'package:app/features/auth/auth_model.dart';
import 'package:app/features/documents/documents_controller.dart';
import 'package:app/features/documents/document_model.dart';

class _FakeDocsController extends DocumentsController {
  @override
  Future<List<DocumentItem>> build() async => [];
}

void main() {
  testWidgets('Render app shell as authenticated on desktop', (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final authUser = AuthUser(
      id: 1,
      email: 'admin@localhost',
      displayName: 'Admin',
      isAdmin: true,
      mustChangePassword: false,
      createdAt: DateTime.now(),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            (ref) => _StaticAuthController(AuthState.authenticated(authUser)),
          ),
          documentsControllerProvider.overrideWith(() => _FakeDocsController()),
        ],
        child: Consumer(
          builder: (context, ref, _) {
            final router = createAppRouter(ref);
            return MaterialApp.router(routerConfig: router);
          },
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
  });

  testWidgets('Render app shell as authenticated on mobile', (tester) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final authUser = AuthUser(
      id: 1,
      email: 'admin@localhost',
      displayName: 'Admin',
      isAdmin: true,
      mustChangePassword: false,
      createdAt: DateTime.now(),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            (ref) => _StaticAuthController(AuthState.authenticated(authUser)),
          ),
          documentsControllerProvider.overrideWith(() => _FakeDocsController()),
        ],
        child: Consumer(
          builder: (context, ref, _) {
            final router = createAppRouter(ref);
            return MaterialApp.router(routerConfig: router);
          },
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
  });
}

class _StaticAuthController extends StateNotifier<AuthState> implements AuthController {
  _StaticAuthController(super.state);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
