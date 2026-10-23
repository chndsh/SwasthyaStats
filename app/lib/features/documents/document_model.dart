class DocumentPageItem {
  final int id;
  final int pageNo;
  final int? width;
  final int? height;

  DocumentPageItem({
    required this.id,
    required this.pageNo,
    this.width,
    this.height,
  });

  factory DocumentPageItem.fromJson(Map<String, dynamic> json) {
    return DocumentPageItem(
      id: json['id'] as int,
      pageNo: json['page_no'] as int,
      width: json['width'] as int?,
      height: json['height'] as int?,
    );
  }
}

class DocumentItem {
  final int id;
  final String filename;
  final String status;
  final String? doctorName;
  final int pageCount;
  final DateTime createdAt;
  final List<DocumentPageItem> pages;

  DocumentItem({
    required this.id,
    required this.filename,
    required this.status,
    this.doctorName,
    required this.pageCount,
    required this.createdAt,
    this.pages = const [],
  });

  factory DocumentItem.fromJson(Map<String, dynamic> json) {
    final pagesList = (json['pages'] as List<dynamic>?)
            ?.map((p) => DocumentPageItem.fromJson(p as Map<String, dynamic>))
            .toList() ??
        [];

    return DocumentItem(
      id: json['id'] as int,
      filename: json['filename'] as String? ?? 'Untitled',
      status: json['status'] as String? ?? 'queued',
      doctorName: json['doctor_name'] as String?,
      pageCount: json['page_count'] as int? ?? 1,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      pages: pagesList,
    );
  }
}
