import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'features/navigation/app_router.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    const ProviderScope(
      child: SwasthyaStatsApp(),
    ),
  );
}

class SwasthyaStatsApp extends StatelessWidget {
  const SwasthyaStatsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'SwasthyaStats',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      routerConfig: appRouter,
    );
  }
}
