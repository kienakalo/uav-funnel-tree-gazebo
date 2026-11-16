# Quy tắc làm việc với kết quả thực nghiệm

## Nguồn gốc và khả năng tái lập

- Khi thêm hoặc cập nhật kết quả JSON, CSV, bảng hoặc hình số liệu, phải lưu script sinh kết quả trong repo và ghi câu lệnh chạy, thư mục làm việc, tham số và đầu vào tương ứng. Không chỉ mô tả file chứa gì trong README.
- Nếu phép tính được chạy bằng lệnh hoặc đoạn mã tạm, chuyển logic cần thiết thành script được lưu trước khi coi đầu ra là kết quả chính thức. Chưa có cách tái tạo thì ghi rõ là thử nghiệm chưa hoàn thiện, không dùng làm bằng chứng trong bài báo.
- Metadata hoặc tài liệu đi kèm phải phân biệt: lập đường hình học, tích phân ngoại tuyến, mô phỏng Gazebo và hình minh họa. Không diễn giải kết quả ngoại tuyến thành kết quả Gazebo.
- Khi so sánh trước/sau, ghi rõ cấu hình và các file đầu vào, kết quả của cả hai lượt; dùng SHA256 để đối chiếu khi cần. Không chỉ lưu số liệu tổng hợp.
- Ghi phiên bản thư viện, môi trường, phạm vi và giới hạn của phép đo khi ảnh hưởng đến cách diễn giải. Ghi số lần đo và điều kiện cache đối với hiệu năng.
- Ảnh chụp, chú thích và biên bản bảo trì không bắt buộc có mô phỏng sinh ra; phải ghi nguồn ảnh và cách chỉnh sửa hoặc mục đích của biên bản. Giữ ảnh gốc.
- Mỗi đầu ra được giữ trong Git phải có lý do lưu và nguồn sinh hoặc nguồn cung cấp xác định. Kiểm tra `.gitignore` để file cần chia sẻ thực sự xuất hiện trong Git.
- Khi lưu kết quả, in `Save at: <đường dẫn>`.

## Dọn dữ liệu cũ

- Trước khi xóa, kiểm tra nơi đọc file, tài liệu dẫn tới file và phụ thuộc SHA256. Cập nhật các liên kết và cấu hình liên quan nếu xóa.
- Không thấy tên file trong mã chưa có nghĩa là file thừa: tên có thể được ghép lúc chạy, hoặc file được dùng để đối chiếu thủ công.
- Trước khi bỏ kết quả cũ, kiểm tra còn dùng ở bước nào không và thống nhất trong nhóm.

## Ghi chú dọn dữ liệu ngày 15/11/2026

- Bỏ `offline_validation.json`, `offline_urban_validation.json`, `reference_fixed.json` ở gốc repo vì thiếu mã sinh và đầu vào để chạy lại. Bỏ các chỗ nhắc tới chúng trong README và tài liệu thử nghiệm.
- Bỏ `map_improvement.json`, `timing_comparison.json` trong `generated/funnel_physics/surface_delivery/` vì thiếu bộ dữ liệu trước/sau để kiểm tra lại. Bỏ các ngoại lệ tương ứng trong `.gitignore`.
- Khi cần tra cứu các file cũ, xem lịch sử Git.
