import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'documents_controller.dart';
import '../../core/api_client.dart';

class DocumentsScreen extends ConsumerStatefulWidget {
  const DocumentsScreen({super.key});

  @override
  ConsumerState<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends ConsumerState<DocumentsScreen> {
  bool _isUploading = false;

  Color _getStatusColor(String status) {
    switch (status) {
      case 'needs_review':
        return Colors.orange;
      case 'confirmed':
        return Colors.green;
      case 'failed':
        return Colors.red;
      case 'ocr':
      case 'normalizing':
      case 'queued':
      case 'extracting':
        return Colors.blue;
      case 'rate_limited':
        return Colors.amber.shade800;
      default:
        return Colors.grey;
    }
  }

  Future<void> _handleCameraCapture(BuildContext context) async {
    final picker = ImagePicker();
    final List<MultipartFile> filesToUpload = [];

    while (true) {
      final XFile? photo = await picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 2400,
        imageQuality: 85,
      );

      if (photo == null) break;

      final bytes = await photo.readAsBytes();
      filesToUpload.add(
        MultipartFile.fromBytes(bytes, filename: photo.name.isNotEmpty ? photo.name : 'photo_${filesToUpload.length + 1}.jpg'),
      );

      if (!context.mounted) break;

      // Ask if user wants to add another page
      final bool? addMore = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Page ${filesToUpload.length} captured'),
          content: const Text('Would you like to capture another page for this document?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Finish & Upload'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Add Another Page'),
            ),
          ],
        ),
      );

      if (addMore != true) break;
    }

    if (filesToUpload.isNotEmpty && context.mounted) {
      await _upload(filesToUpload);
    }
  }

  Future<void> _handleFilePick(BuildContext context) async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      withData: true,
      type: FileType.custom,
      allowedExtensions: ['png', 'jpg', 'jpeg', 'pdf'],
    );

    if (result != null && result.files.isNotEmpty) {
      final List<MultipartFile> filesToUpload = [];
      for (final file in result.files) {
        if (file.bytes != null) {
          filesToUpload.add(
            MultipartFile.fromBytes(file.bytes!, filename: file.name),
          );
        }
      }

      if (filesToUpload.isNotEmpty && context.mounted) {
        await _upload(filesToUpload);
      }
    }
  }

  Future<void> _upload(List<MultipartFile> files) async {
    setState(() => _isUploading = true);
    try {
      await ref.read(documentsControllerProvider.notifier).uploadFiles(files);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document uploaded successfully. Processing started.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  void _showAddDocumentSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const ListTile(
                title: Text('Add New Document', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE6FFFA),
                  child: Icon(Icons.camera_alt, color: Color(0xFF0D9488)),
                ),
                title: const Text('Take Photo (Camera)'),
                subtitle: const Text('Sequential multi-page capture'),
                onTap: () {
                  Navigator.pop(ctx);
                  _handleCameraCapture(context);
                },
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE6FFFA),
                  child: Icon(Icons.file_upload, color: Color(0xFF0D9488)),
                ),
                title: const Text('Upload Images or PDF (Batch)'),
                subtitle: const Text('Pick one or more files from your device'),
                onTap: () {
                  Navigator.pop(ctx);
                  _handleFilePick(context);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final docsAsync = ref.watch(documentsControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Documents'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () => ref.read(documentsControllerProvider.notifier).refresh(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _isUploading ? null : () => _showAddDocumentSheet(context),
        backgroundColor: const Color(0xFF0D9488),
        child: _isUploading
            ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
            : const Icon(Icons.add, color: Colors.white),
      ),
      body: docsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: Colors.red),
                const SizedBox(height: 16),
                Text('Failed to load documents: $err', textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => ref.read(documentsControllerProvider.notifier).refresh(),
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
        data: (docs) {
          if (docs.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.description_outlined, size: 64, color: Colors.grey.shade400),
                    const SizedBox(height: 16),
                    const Text('No documents uploaded yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Text(
                      'Use the + button below to scan a lab report with your camera or upload a file.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey.shade600),
                    ),
                  ],
                ),
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () => ref.read(documentsControllerProvider.notifier).refresh(),
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              itemCount: docs.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final doc = docs[index];
                final statusColor = _getStatusColor(doc.status);

                return ListTile(
                  contentPadding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
                  leading: CircleAvatar(
                    backgroundColor: statusColor.withValues(alpha: 0.12),
                    child: Icon(Icons.description, color: statusColor),
                  ),
                  title: Text(doc.filename, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(
                    '${doc.pageCount} page${doc.pageCount > 1 ? 's' : ''} • ${_formatDate(doc.createdAt)}',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                  ),
                  trailing: InkWell(
                    onTap: (doc.status == 'rate_limited' || doc.status == 'failed')
                        ? () async {
                            try {
                              final client = ref.read(apiClientProvider);
                              await client.dio.post('/documents/${doc.id}/retry');
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Retrying extraction...')),
                                );
                              }
                              ref.read(documentsControllerProvider.notifier).refresh();
                            } catch (e) {
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text('Retry failed: $e'), backgroundColor: Colors.red),
                                );
                              }
                            }
                          }
                        : null,
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: statusColor.withValues(alpha: 0.4)),
                      ),
                      child: Text(
                        doc.status == 'rate_limited'
                            ? 'Rate limited (tap to retry)'
                            : doc.status == 'failed'
                                ? 'Failed (tap to retry)'
                                : doc.status,
                        style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 12),
                      ),
                    ),
                  ),
                  onTap: () {
                    if (doc.status == 'needs_review' || doc.status == 'confirmed') {
                      context.go('/documents/${doc.id}/review');
                    } else if (doc.status == 'rate_limited' || doc.status == 'failed') {
                      // Tap on tile also triggers retry
                      ref.read(apiClientProvider).dio.post('/documents/${doc.id}/retry').then((_) {
                        ref.read(documentsControllerProvider.notifier).refresh();
                      });
                    } else {
                      context.go('/documents/${doc.id}');
                    }
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
