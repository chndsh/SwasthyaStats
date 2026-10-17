import 'package:flutter/material.dart';

class LabDetailScreen extends StatelessWidget {
  final String testName;

  const LabDetailScreen({super.key, required this.testName});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(testName)),
      body: Center(
        child: Text('Trend chart for $testName'),
      ),
    );
  }
}
