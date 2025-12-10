import 'dart:async';
import 'dart:math';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ImageFetcherScreen extends StatefulWidget {
  const ImageFetcherScreen({Key? key}) : super(key: key);

  @override
  State<ImageFetcherScreen> createState() => _ImageFetcherScreenState();
}

class _ImageFetcherScreenState extends State<ImageFetcherScreen> {
  String? imageUrl;
  String? imageUrl2;
  String? area;
  String? pixel;
  String? percentage;
  bool isLoading = false;
  TransformationController controller = TransformationController();
  TapDownDetails? tapDownDetails;

  Future<void> fetchImage() async {
    setState(() {
      isLoading = true;
    });

    try {
      // Using Unsplash API as an example
      // Replace with your preferred image API endpoint
      Map<String, String> requestHeaders = {
        'X-Api-Key': 'SQpc7nYGBjIPBiHI47Ezjw==M6Fmfih2Z7KZVkOs',
        'Accept': 'image/jpg',
      };
      final response = await http.get(
          Uri.parse('http://10.183.80.227:8000/captureImage2'),
          headers: requestHeaders);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print(data["file"].toString());
        print("http://10.183.80.227:8000/openImage?image_path=" +
            data["original_image_path"].toString());
        setState(() {
          imageUrl = "http://10.183.80.227:8000/openImage?image_path=" +
              data["graded_image_path"].toString();
          imageUrl2 = "http://10.183.80.227:8000/openImage?image_path=" +
              data["original_image_path"].toString();
          area = data["total_detected_objects"].toString();
          pixel = data["total_area_pixels"].toString();
          percentage = data["total_area_percentage"].toString();
          isLoading = false;
        });
      } else {
        setState(() {
          imageUrl = null;
          imageUrl2 = null;
          isLoading = false;
        });
        _showErrorDialog('Failed to load image');
      }
    } catch (e) {
      setState(() {
        imageUrl = null;
        imageUrl2 = null;
        isLoading = false;
      });
      _showErrorDialog('Error: $e');
    }
  }

  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  final double aspectRatio = 16 / 9;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Deteksi Aflatoksin'),
      ),
      body: SingleChildScrollView(
        child: Center(
          child: Container(
            margin: const EdgeInsets.only(top: 15),
            width: min(MediaQuery.of(context).size.width, 900),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  margin: EdgeInsets.only(
                      bottom: MediaQuery.of(context).size.width * 0.01),
                  child: Card(
                      elevation: 10,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 15, vertical: 15),
                        child: Column(
                          children: [
                            const Padding(
                              padding: EdgeInsets.only(bottom: 15),
                              child: Text(
                                'Deteksi Aflatoksin',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            const Padding(
                              padding: EdgeInsets.only(bottom: 15),
                              child: Text(
                                'Klik tombol di bawah untuk mengambil gambar dan mendeteksi aflatoksin',
                                style: TextStyle(
                                  fontSize: 16,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            ElevatedButton(
                              onPressed: isLoading ? null : fetchImage,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.pink,
                                textStyle: const TextStyle(
                                  color: Colors.white,
                                ),
                                padding: const EdgeInsets.all(25),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(30),
                                ),
                              ),
                              child: Text(
                                  isLoading ? 'Loading...' : 'Fetch Image'),
                            ),
                          ],
                        ),
                      )),
                ),
                Builder(builder: (context) {
                  if (isLoading) {
                    return const Center(
                      child: SizedBox(
                        width: 50,
                        height: 50,
                        child: CircularProgressIndicator(),
                      ),
                    );
                  } else if (imageUrl != null&&imageUrl2 != null) {
                    return Card(
                        margin: const EdgeInsets.only(bottom: 30),
                        elevation: 10,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 15, vertical: 20),
                          child: Column(
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(15),
                                child: AspectRatio(
                                  aspectRatio: aspectRatio,
                                  child: GestureDetector(
                                    onDoubleTapDown: (details) =>
                                        tapDownDetails = details,
                                    onDoubleTap: () {
                                      // Handle double tap if needed
                                      final position =
                                          tapDownDetails!.localPosition;

                                      final double scale = 3.0;
                                      final x = -position.dx * (scale - 1);
                                      final y = -position.dy * (scale - 1);
                                      final zoomed = Matrix4.identity()
                                        ..translate(x, y)
                                        ..scale(scale);

                                      final value = controller.value.isIdentity()?zoomed:Matrix4.identity();
                                      controller.value = value;
                                    },
                                    child: InteractiveViewer(
                                      // clipBehavior: Clip.none,
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl!,
                                        // loadingBuilder: (context, child, loadingProgress) {
                                        //   if (loadingProgress == null) return child;
                                        //   return Center(
                                        //     child: CircularProgressIndicator(
                                        //       value: loadingProgress.expectedTotalBytes != null
                                        //           ? loadingProgress.cumulativeBytesLoaded /
                                        //               loadingProgress.expectedTotalBytes!
                                        //           : null,
                                        //     ),
                                        //   );
                                        // },
                                        // errorBuilder: (context, error, stackTrace) {
                                        //   return const Center(
                                        //     child: Text('Failed to load image'),
                                        //   );
                                        // },
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                              Padding(
                                padding: const EdgeInsets.all(15),
                                child: AspectRatio(
                                  aspectRatio: aspectRatio,
                                  child: GestureDetector(
                                    onDoubleTapDown: (details) =>
                                        tapDownDetails = details,
                                    onDoubleTap: () {
                                      // Handle double tap if needed
                                      final position =
                                          tapDownDetails!.localPosition;

                                      final double scale = 3.0;
                                      final x = -position.dx * (scale - 1);
                                      final y = -position.dy * (scale - 1);
                                      final zoomed = Matrix4.identity()
                                        ..translate(x, y)
                                        ..scale(scale);

                                      final value = controller.value.isIdentity()?zoomed:Matrix4.identity();
                                      controller.value = value;
                                    },
                                    child: InteractiveViewer(
                                      // clipBehavior: Clip.none,
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl2!,
                                        // loadingBuilder: (context, child, loadingProgress) {
                                        //   if (loadingProgress == null) return child;
                                        //   return Center(
                                        //     child: CircularProgressIndicator(
                                        //       value: loadingProgress.expectedTotalBytes != null
                                        //           ? loadingProgress.cumulativeBytesLoaded /
                                        //               loadingProgress.expectedTotalBytes!
                                        //           : null,
                                        //     ),
                                        //   );
                                        // },
                                        // errorBuilder: (context, error, stackTrace) {
                                        //   return const Center(
                                        //     child: Text('Failed to load image'),
                                        //   );
                                        // },
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                              Padding(
                                padding:
                                    const EdgeInsets.fromLTRB(15, 0, 15, 15),
                                child: Container(
                                  width: double.infinity,
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(15),
                                    color: Colors.grey[200],
                                  ),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 30, vertical: 15),
                                    child: Table(
                                      border: TableBorder(
                                          horizontalInside: BorderSide(
                                              color: Colors.grey[300]!)),
                                      children: [
                                        TableRow(children: [
                                          const Padding(
                                            padding: EdgeInsets.all(10),
                                            child: Text(
                                              'Jumlah Aflatoksin:',
                                              style: TextStyle(
                                                fontWeight: FontWeight.bold,
                                                color: Colors.blue,
                                              ),
                                            ),
                                          ),
                                          Padding(
                                            padding: const EdgeInsets.all(10),
                                            child: Text(area ?? "0"),
                                          ),
                                        ]),
                                        TableRow(children: [
                                          Padding(
                                            padding: EdgeInsets.all(10),
                                            child: Text(
                                              'presentase pixel:',
                                              style: TextStyle(
                                                fontWeight: FontWeight.bold,
                                                color: Colors.blue,
                                              ),
                                            ),
                                          ),
                                          Padding(
                                            padding: EdgeInsets.all(10),
                                            child: Text('${percentage!}%'),
                                          ),
                                        ]),
                                        TableRow(children: [
                                          Padding(
                                            padding: EdgeInsets.all(10),
                                            child: Text(
                                              'Jumlah pixel:',
                                              style: TextStyle(
                                                fontWeight: FontWeight.bold,
                                                color: Colors.blue,
                                              ),
                                            ),
                                          ),
                                          Padding(
                                            padding: EdgeInsets.all(10),
                                            child: Text('${pixel!} px'),
                                          ),
                                        ]),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ));
                  } else {
                    return const Center(
                      child: Text('No image to display'),
                    );
                  }
                }),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
