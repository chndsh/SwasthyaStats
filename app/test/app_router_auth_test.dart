import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app/features/auth/auth_controller.dart';
import 'package:app/features/auth/auth_model.dart';
import 'package:app/features/auth/token_storage.dart';
import 'package:app/features/navigation/app_router.dart';

class _Storage implements TokenStorage {
  final bool hasSession;

  _Storage(this.hasSession);

  @override
  Future<String?> readAccessToken() async => hasSession ? 'access' : null;
  @override
  Future<String?> readRefreshToken() async => hasSession ? 'refresh' : null;
  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {}
  @override
  Future<void> clear() async {}
  @override
  Future<bool> hasCompleteSession() async => hasSession;
}

class _Service implements AuthService {
  @override
  Future<TokenPair> login({
    required String email,
    required String password,
  }) async => const TokenPair(accessToken: 'access', refreshToken: 'refresh');

  @override
  Future<AuthUser> currentUser() async => AuthUser(
    id: 1,
    email: 'user@example.com',
    displayName: null,
    isAdmin: false,
    mustChangePassword: false,
    createdAt: DateTime.utc(2026),
  );

  @override
  Future<void> logout({required String refreshToken}) async {}

  @override
  Future<AuthUser> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async => currentUser();
}

class _RouterHost extends ConsumerWidget {
  const _RouterHost();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(routerConfig: createAppRouter(ref));
  }
}

void main() {
  testWidgets('unauthenticated users are redirected to login', (tester) async {
    final controller = AuthController(
      tokenStorage: _Storage(false),
      authService: _Service(),
    );
    await controller.initialize();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [authControllerProvider.overrideWith((ref) => controller)],
        child: const _RouterHost(),
      ),
    );
    await tester.pump();

    expect(find.text('Sign in to SwasthyaStats'), findsOneWidget);
  });

  test('authenticated users are redirected away from login', () {
    expect(
      authRedirect(
        authState: AuthState.authenticated(
          AuthUser(
            id: 1,
            email: 'user@example.com',
            displayName: null,
            isAdmin: false,
            mustChangePassword: false,
            createdAt: DateTime.utc(2026),
          ),
        ),
        location: '/login',
        requestedLocation: '/login',
      ),
      '/documents',
    );
  });

  test('temporary-password users are redirected to change password', () {
    expect(
      authRedirect(
        authState: AuthState.authenticated(
          AuthUser(
            id: 1,
            email: 'user@example.com',
            displayName: null,
            isAdmin: false,
            mustChangePassword: true,
            createdAt: DateTime.utc(2026),
          ),
        ),
        location: '/documents',
        requestedLocation: '/documents',
      ),
      '/change-password?redirect=%2Fdocuments',
    );
    expect(
      authRedirect(
        authState: AuthState.authenticated(
          AuthUser(
            id: 1,
            email: 'user@example.com',
            displayName: null,
            isAdmin: false,
            mustChangePassword: true,
            createdAt: DateTime.utc(2026),
          ),
        ),
        location: '/change-password',
        requestedLocation: '/change-password',
      ),
      isNull,
    );
  });

  test('non-admin users cannot open admin users route', () {
    expect(
      authRedirect(
        authState: AuthState.authenticated(
          AuthUser(
            id: 1,
            email: 'user@example.com',
            displayName: null,
            isAdmin: false,
            mustChangePassword: false,
            createdAt: DateTime.utc(2026),
          ),
        ),
        location: '/admin/users',
        requestedLocation: '/admin/users',
      ),
      '/documents',
    );
  });
}
