import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app/features/auth/auth_controller.dart';
import 'package:app/features/auth/auth_model.dart';
import 'package:app/features/auth/login_screen.dart';
import 'package:app/features/auth/token_storage.dart';

class _NoopStorage implements TokenStorage {
  @override
  Future<String?> readAccessToken() async => null;
  @override
  Future<String?> readRefreshToken() async => null;
  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {}
  @override
  Future<void> clear() async {}

  @override
  Future<bool> hasCompleteSession() async => false;
}

void main() {
  testWidgets('validates required fields', (tester) async {
    final controller = AuthController(
      tokenStorage: _NoopStorage(),
      authService: _FakeAuthService(),
    );
    await controller.initialize();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authControllerProvider.overrideWith((ref) => controller)],
        child: const MaterialApp(home: LoginScreen()),
      ),
    );

    await tester.tap(find.text('Sign in'));
    await tester.pump();

    expect(find.text('Enter your email'), findsOneWidget);
    expect(find.text('Enter your password'), findsOneWidget);
  });
}

class _FakeAuthService implements AuthService {
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
