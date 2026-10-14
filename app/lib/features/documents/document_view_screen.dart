import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/api_client.dart';
import 'document_model.dart';

class DocumentViewScreen extends ConsumerStatefulWidget {
  final int documentId;

  const DocumentViewScreen({super.key, required this.documentId});

  @override
  ConsumerState<DocumentViewScreen> createState() => _DocumentViewScreenState();
}

class _DocumentViewScreenState extends ConsumerState<DocumentViewScreen> {
  DocumentItem? _document;
  bool _isLoading = true;
  String? _error;
  int _currentPage = 1;
  Uint8List? _imageBytes;
  bool _isLoadingImage = false;

  @override
  void initState() {
    super.initState();
    _loadDocument();
  }

  Future<void> _loadDocument() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final client = ref.read(apiClientProvider);
      final resp = await client.dio.get('/documents/${widget.documentId}');
      final doc = DocumentItem.fromJson(resp.data as Map<String, dynamic>);
      setState(() {
        _document = doc;
        _isLoading = false;
      });
      await _loadPageImage(_currentPage);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _loadPageImage(int pageNo) async {
    setState(() => _isLoadingImage = true);
    try {
      final client = ref.read(apiClientProvider);
      final resp = await client.dio.get<List<int>>(
        '/documents/${widget.documentId}/pages/$pageNo.png',
        options: Options(responseType: ResponseType.bytes),
      );
      if (resp.data != null) {
        setState(() {
          _imageBytes = Uint8List.fromList(resp.data!);
          _currentPage = pageNo;
          _isLoadingImage = false;
        });
      }
    } catch (e) {
      setState(() => _isLoadingImage = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Document View')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null || _document == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Document View')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error loading document: $_error'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _loadDocument, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    final doc = _document!;
    final totalPages = doc.pageCount;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/documents'),
        ),
        title: Text(doc.filename, style: const TextStyle(fontSize: 16)),
        actions: [
          Chip(
            label: Text(doc.status, style: const TextStyle(fontSize: 12)),
            backgroundColor: const Color(0xFFE6FFFA),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          if (totalPages > 1)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.grey.shade100,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  IconButton(
                    icon: const Icon(Icons.chevron_left),
                    onPressed: _currentPage > 1 ? () => _loadPageImage(_currentPage - 1) : null,
                  ),
                  Text('Page $_currentPage of $totalPages', style: const TextStyle(fontWeight: FontWeight.w600)),
                  IconButton(
                    icon: const Icon(Icons.chevron_right),
                    onPressed: _currentPage < totalPages ? () => _loadPageImage(_currentPage + 1) : null,
                  ),
                ],
              ),
            ),
          Expanded(
            child: _isLoadingImage
                ? const Center(child: CircularProgressIndicator())
                : _imageBytes != null
                    ? InteractiveViewer(
                        minScale: 0.5,
                        maxScale: 4.0,
                        child: Center(
                          child: Image.memory(
                            _imageBytes!,
                            fit: BoxFit.contain,
                          ),
                        ),
                      )
                    : const Center(
                        child: Text('Page image not yet available or document is processing.'),
                      ),
          ),
        ],
      ),
    );
  }
}
