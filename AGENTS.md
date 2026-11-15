# Quy tắc làm việc với kết quả thực nghiệm

## Nguồn gốc và khả năng tái lập

- Khi thêm hoặc cập nhật kết quả JSON, CSV, bảng hoặc hình số liệu, phải lưu script sinh kết quả trong repo và ghi câu lệnh chạy, thư mục làm việc, tham số và đầu vào tương ứng. Không chỉ mô tả file chứa gì trong README.
- Nếu phép tính được chạy bằng lệnh hoặc đoạn mã tạm, chuyển logic cần thiết thành script được lưu trước khi coi đầu ra là kết quả chính thức. Chưa có cách tái tạo thì ghi rõ là thử nghiệm chưa hoàn thiện, không dùng làm bằng chứng trong bài báo.
- Metadata hoặc tài liệu đi kèm phải phân biệt: lập đường hình học, tích phân ngoại tuyến, mô phỏng Gazebo và hình minh họa. Không diễn giải kết quả ngoại tuyến thành kết quả Gazebo.
- Với so sánh trước/sau, lưu cấu hình và danh tính của cả hai bộ đầu vào/kết quả; dùng SHA256 khi thích hợp. Không lưu riêng các con số tổng hợp thiếu nguồn.
- Ghi phiên bản thư viện, môi trường, phạm vi và giới hạn của phép đo khi ảnh hưởng đến cách diễn giải. Ghi số lần đo và điều kiện cache đối với hiệu năng.
- Ảnh chụp, chú thích và biên bản bảo trì không bắt buộc có mô phỏng sinh ra; phải ghi nguồn ảnh và cách chỉnh sửa hoặc mục đích của biên bản. Giữ ảnh gốc.
- Mỗi đầu ra được giữ trong Git phải có lý do lưu và nguồn sinh hoặc nguồn cung cấp xác định. Kiểm tra `.gitignore` để file cần chia sẻ thực sự xuất hiện trong Git.
- Khi lưu kết quả, in `Save at: <đường dẫn>`.

## Dọn dữ liệu cũ

- Trước khi xóa, kiểm tra nơi đọc file, tài liệu dẫn tới file và phụ thuộc SHA256. Cập nhật các liên kết và cấu hình liên quan nếu xóa.
- Không kết luận file thừa chỉ vì không thấy tên literal trong mã: có thể tên được ghép động hoặc là đầu vào/tham chiếu thủ công.
- Không xóa kết quả cũ chỉ vì có kết quả mới; cần xác định phạm vi, phụ thuộc và sự cho phép của người dùng.

## Bối cảnh rà soát ngày 2026-11-15

- Người dùng yêu cầu xóa `offline_validation.json`, `offline_urban_validation.json` và `reference_fixed.json` ở gốc repo vì thiếu quy trình tái tạo rõ ràng. Các tham chiếu trong README và tài liệu thử nghiệm đã được sửa.
- Người dùng đã yêu cầu xóa `generated/funnel_physics/surface_delivery/map_improvement.json` và `timing_comparison.json`; cả hai file và các ngoại lệ tương ứng trong `.gitignore` đã được xóa.
- Không suy ra trạng thái hiện tại từ ghi chú này: luôn kiểm tra Git và filesystem trước khi hành động.
