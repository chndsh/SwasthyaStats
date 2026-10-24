import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'auth_controller.dart';

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  ConsumerState<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final success = await ref.read(authControllerProvider.notifier).changePassword(
          currentPassword: _current.text,
          newPassword: _next.text,
        );
    if (!mounted) return;
    setState(() => _loading = false);
    if (success) {
      final redirect = GoRouterState.of(context).uri.queryParameters['redirect'];
      context.go(redirect ?? '/documents');
    } else {
      setState(() => _error = 'Unable to change password. Check your current password and try again.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Change password')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Choose a new password before continuing.'),
                  const SizedBox(height: 20),
                  TextFormField(
                    controller: _current,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Current password'),
                    validator: (value) => value == null || value.isEmpty ? 'Enter your current password' : null,
                  ),
                  TextFormField(
                    controller: _next,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'New password'),
                    validator: (value) => value == null || value.length < 8 ? 'Use at least 8 characters' : null,
                  ),
                  TextFormField(
                    controller: _confirm,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Confirm new password'),
                    validator: (value) => value != _next.text ? 'Passwords do not match' : null,
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _loading ? null : _submit,
                    child: _loading ? const CircularProgressIndicator() : const Text('Change password'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
