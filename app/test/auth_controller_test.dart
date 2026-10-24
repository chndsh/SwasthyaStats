import 'package:flutter_test/flutter_test.dart';
import 'package:app/features/auth/auth_controller.dart';
import 'package:app/features/auth/auth_model.dart';
import 'package:app/features/auth/token_storage.dart';

class _FakeStorage implements TokenStorage {
  String? access;
  String? refresh;

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<String?> readRefreshToken() async => refresh;

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }

  @override
  Future<bool> hasCompleteSession() async {
    return access != null &&
        access!.isNotEmpty &&
        refresh != null &&
        refresh!.isNotEmpty;
  }
}

class _FakeAuthService implements AuthService {
  TokenPair pair = const TokenPair(accessToken: 'access', refreshToken: 'refresh');
  AuthUser user = AuthUser(
    id: 1,
    email: 'user@example.com',
    displayName: 'User',
    isAdmin: false,
    mustChangePassword: false,
    createdAt: DateTime.utc(2026, 1, 1),
  );
  Object? loginError;
  Object? logoutError;
  Object? passwordError;
  int currentUserCalls = 0;

  @override
  Future<TokenPair> login({
    required String email,
    required String password,
  }) async {
    if (loginError != null) throw loginError!;
    return pair;
  }

  @override
  Future<AuthUser> currentUser() async {
    currentUserCalls++;
    return user;
  }

  @override
  Future<void> logout({required String refreshToken}) async {
    if (logoutError != null) throw logoutError!;
  }

  @override
  Future<AuthUser> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    if (passwordError != null) throw passwordError!;
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
}

void main() {
  test('startup without tokens is unauthenticated', () async {
    final controller = AuthController(
      tokenStorage: _FakeStorage(),
      authService: _FakeAuthService(),
    );

    await controller.initialize();

    expect(controller.state.status, AuthStatus.unauthenticated);
  });

  test('startup with tokens loads the current user', () async {
    final storage = _FakeStorage()
      ..access = 'access'
      ..refresh = 'refresh';
    final service = _FakeAuthService();
    final controller = AuthController(
      tokenStorage: storage,
      authService: service,
    );

    await controller.initialize();

    expect(controller.state.isAuthenticated, isTrue);
    expect(controller.state.user?.email, 'user@example.com');
    expect(service.currentUserCalls, 1);
  });

  test('login stores tokens and loads the current user', () async {
    final storage = _FakeStorage();
    final controller = AuthController(
      tokenStorage: storage,
      authService: _FakeAuthService(),
    );

    expect(
      await controller.login(email: 'user@example.com', password: 'secret'),
      isTrue,
    );
    expect(storage.access, 'access');
    expect(storage.refresh, 'refresh');
    expect(controller.state.isAuthenticated, isTrue);
  });

  test('invalid credentials remain unauthenticated', () async {
    final storage = _FakeStorage();
    final service = _FakeAuthService()..loginError = StateError('invalid');
    final controller = AuthController(
      tokenStorage: storage,
      authService: service,
    );

    expect(
      await controller.login(email: 'user@example.com', password: 'wrong'),
      isFalse,
    );
    expect(controller.state.status, AuthStatus.unauthenticated);
    expect(controller.state.errorMessage, isNotNull);
    expect(await storage.hasCompleteSession(), isFalse);
  });

  test('logout clears tokens even when the server fails', () async {
    final storage = _FakeStorage()
      ..access = 'access'
      ..refresh = 'refresh';
    final service = _FakeAuthService()..logoutError = StateError('offline');
    final controller = AuthController(
      tokenStorage: storage,
      authService: service,
    );

    await controller.logout();

    expect(await storage.hasCompleteSession(), isFalse);
    expect(controller.state.status, AuthStatus.unauthenticated);
  });
}
