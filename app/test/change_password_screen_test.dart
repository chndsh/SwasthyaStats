import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/features/auth/auth_controller.dart';
import 'package:app/features/auth/auth_model.dart';
import 'package:app/features/auth/change_password_screen.dart';
import 'package:app/features/auth/token_storage.dart';

class _Storage implements TokenStorage {
  @override
  Future<String?> readAccessToken() async => 'access';
  @override
  Future<String?> readRefreshToken() async => 'refresh';
  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {}
  @override
  Future<void> clear() async {}
  @override
  Future<bool> hasCompleteSession() async => true;
}

class _Service implements AuthService {
  AuthUser user = AuthUser(
    id: 1,
    email: 'user@example.com',
    displayName: null,
    isAdmin: false,
    mustChangePassword: true,
    createdAt: DateTime.utc(2026),
  );

  @override
  Future<TokenPair> login({
    required String email,
    required String password,
  }) async => const TokenPair(accessToken: 'access', refreshToken: 'refresh');
  @override
  Future<AuthUser> currentUser() async => user;
  @override
  Future<AuthUser> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    user = AuthUser(
      id: user.id,
      email: user.email,
      displayName: user.displayName,
      isAdmin: user.isAdmin,
      mustChangePassword: false,
      createdAt: user.createdAt,
    );
    return user;
  }

  @override
  Future<void> logout({required String refreshToken}) async {}
}

void main() {
  testWidgets('validates confirmation and password length', (tester) async {
    final controller = AuthController(
      tokenStorage: _Storage(),
      authService: _Service(),
    );
    await controller.initialize();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authControllerProvider.overrideWith((ref) => controller)],
        child: const MaterialApp(home: ChangePasswordScreen()),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Change password'));
    await tester.pump();
    expect(find.text('Enter your current password'), findsOneWidget);
    expect(find.text('Use at least 8 characters'), findsOneWidget);
  });
}
