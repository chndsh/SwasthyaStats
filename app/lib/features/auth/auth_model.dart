import 'package:flutter/foundation.dart';

enum AuthStatus {
  loading,
  unauthenticated,
  authenticated,
  error,
}

class AuthUser {
  final int id;
  final String email;
  final String? displayName;
  final bool isAdmin;
  final DateTime createdAt;

  const AuthUser({
    required this.id,
    required this.email,
    required this.displayName,
    required this.isAdmin,
    required this.createdAt,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: json['id'] as int,
      email: json['email'] as String,
      displayName: json['display_name'] as String?,
      isAdmin: json['is_admin'] as bool? ?? false,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class AuthState {
  final AuthStatus status;
  final AuthUser? user;
  final String? errorMessage;

  const AuthState._({
    required this.status,
    this.user,
    this.errorMessage,
  });

  const AuthState.loading() : this._(status: AuthStatus.loading);

  const AuthState.unauthenticated({String? errorMessage})
      : this._(
          status: AuthStatus.unauthenticated,
          errorMessage: errorMessage,
        );

  const AuthState.authenticated(AuthUser user)
      : this._(
          status: AuthStatus.authenticated,
          user: user,
        );

  const AuthState.error(String message)
      : this._(
          status: AuthStatus.error,
          errorMessage: message,
        );

  bool get isAuthenticated => status == AuthStatus.authenticated && user != null;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AuthState &&
          status == other.status &&
          user == other.user &&
          errorMessage == other.errorMessage;

  @override
  int get hashCode => Object.hash(status, user, errorMessage);

  @override
  String toString() =>
      'AuthState(status: $status, user: $user, errorMessage: $errorMessage)';
}

@visibleForTesting
AuthUser authUserFromJson(Map<String, dynamic> json) => AuthUser.fromJson(json);
