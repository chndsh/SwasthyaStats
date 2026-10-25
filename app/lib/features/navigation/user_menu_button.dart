import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../auth/auth_controller.dart';

class UserMenuButton extends ConsumerWidget {
  const UserMenuButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    final user = auth.user;
    if (user == null) return const SizedBox.shrink();

    final initial = user.email.isNotEmpty ? user.email[0].toUpperCase() : 'U';

    return PopupMenuButton<String>(
      tooltip: 'Account (${user.email})',
      icon: CircleAvatar(
        radius: 14,
        backgroundColor: const Color(0xFF0D9488),
        child: Text(
          initial,
          style: const TextStyle(
            fontSize: 12,
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      onSelected: (value) {
        if (value == 'admin') {
          context.go('/admin/users');
        } else if (value == 'password') {
          context.go('/change-password');
        } else if (value == 'logout') {
          ref.read(authControllerProvider.notifier).logout();
        }
      },
      itemBuilder: (ctx) => [
        PopupMenuItem<String>(
          enabled: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                user.email,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.black87,
                ),
              ),
              Text(
                user.isAdmin ? 'Administrator' : 'Patient Account',
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
              const Divider(),
            ],
          ),
        ),
        if (user.isAdmin)
          const PopupMenuItem<String>(
            value: 'admin',
            child: Row(
              children: [
                Icon(Icons.manage_accounts, size: 20),
                SizedBox(width: 8),
                Text('Admin Users'),
              ],
            ),
          ),
        const PopupMenuItem<String>(
          value: 'password',
          child: Row(
            children: [
              Icon(Icons.password, size: 20),
              SizedBox(width: 8),
              Text('Change Password'),
            ],
          ),
        ),
        const PopupMenuItem<String>(
          value: 'logout',
          child: Row(
            children: [
              Icon(Icons.logout, size: 20, color: Colors.red),
              SizedBox(width: 8),
              Text('Log Out', style: TextStyle(color: Colors.red)),
            ],
          ),
        ),
      ],
    );
  }
}
