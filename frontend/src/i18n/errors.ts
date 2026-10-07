import type { Language } from '../types';

/** Stable error codes returned by the API in `{ detail, code }` bodies. */
type Messages = Record<string, { fa: string; en: string }>;

const UPLOAD: Messages = {
  unsupported_file: { fa: 'این نوع فایل پشتیبانی نمی‌شود.', en: 'This file type is not supported.' },
  file_type_mismatch: { fa: 'محتوای فایل با پسوند آن هم‌خوان نیست؛ شاید پسوند اشتباه است.', en: 'The file content does not match its extension; the extension may be wrong.' },
  invalid_filename: { fa: 'نام فایل معتبر نیست. نام را کوتاه‌تر و بدون مسیر کنید.', en: 'The file name is invalid. Use a shorter name without a path.' },
  corrupt_file: { fa: 'فایل خراب است یا باز نمی‌شود. آن را دوباره ذخیره و بارگذاری کنید.', en: 'The file is damaged or cannot be opened. Save it again and re-upload.' },
  unsafe_archive: { fa: 'ساختار فایل Office غیرعادی است و برای امنیت پردازش نشد.', en: 'The Office file has an unusual structure and was not processed for safety.' },
  encrypted_document: { fa: 'فایل رمزدار است. نسخهٔ بدون رمز را بارگذاری کنید.', en: 'The file is password-protected. Upload an unprotected copy.' },
  text_encoding: { fa: 'کدگذاری فایل متنی شناخته نشد. آن را با UTF-8 ذخیره کنید.', en: 'The text encoding was not recognized. Save the file as UTF-8.' },
  empty_document: { fa: 'متنی در این فایل پیدا نشد.', en: 'No text was found in this file.' },
  no_readable_text: { fa: 'OCR متن خوانایی در این فایل پیدا نکرد. کیفیت اسکن را بررسی کنید.', en: 'OCR found no readable text. Check the scan quality.' },
  ocr_disabled: { fa: 'این فایل اسکن‌شده است و OCR غیرفعال است.', en: 'This is a scanned file and OCR is disabled.' },
  ocr_unavailable: { fa: 'OCR در دسترس نیست (Tesseract نصب نیست).', en: 'OCR is unavailable (Tesseract is not installed).' },
  ocr_failed: { fa: 'OCR نتوانست این تصویر را بخواند.', en: 'OCR could not read this image.' },
  ocr_timeout: { fa: 'OCR این تصویر بیش از حد طول کشید.', en: 'OCR took too long for this image.' },
  file_too_large: { fa: 'حجم فایل بیشتر از حد مجاز است.', en: 'The file is larger than the allowed size.' },
  batch_too_large: { fa: 'حجم کل فایل‌های این بارگذاری بیشتر از حد مجاز است.', en: 'The upload batch is larger than the allowed size.' },
  too_large: { fa: 'حجم درخواست بیشتر از حد مجاز است.', en: 'The request is larger than allowed.' },
  duplicate_file: { fa: 'فایلی با همین نام در این گفت‌وگو هست.', en: 'A file with this name is already in this conversation.' },
  too_many_files: { fa: 'تعداد فایل‌های این گفت‌وگو به سقف رسیده است.', en: 'This conversation has reached its file limit.' },
  invalid_document: { fa: 'این فایل قابل پردازش نیست.', en: 'This file could not be processed.' },
};

const QUERY: Messages = {
  model_timeout: { fa: 'مدل در زمان مقرر پاسخ نداد. دوباره تلاش کنید یا پرسش را کوتاه‌تر کنید.', en: 'The model did not answer in time. Try again or ask a shorter question.' },
  model_auth: { fa: 'کلید API پذیرفته نشد. در تنظیمات، کلید را بررسی کنید.', en: 'The API key was rejected. Check it in Settings.' },
  model_rate_limited: { fa: 'سرویس مدل محدودیت تعداد درخواست اعمال کرده است. کمی بعد دوباره تلاش کنید.', en: 'The model service is rate-limiting requests. Try again shortly.' },
  model_not_found: { fa: 'مدل انتخاب‌شده روی سرویس پیدا نشد. نام مدل را در تنظیمات بررسی کنید.', en: 'The selected model was not found. Check the model name in Settings.' },
  model_unavailable: { fa: 'سرویس مدل در دسترس نیست. اتصال یا اجرای Ollama را بررسی کنید.', en: 'The model service is unreachable. Check the connection or that Ollama is running.' },
  model_rejected: { fa: 'سرویس مدل درخواست را نپذیرفت.', en: 'The model service rejected the request.' },
  invalid_request: { fa: 'درخواست معتبر نیست؛ اشاره به سندها را بررسی کنید.', en: 'The request is invalid; check the document mentions.' },
  stream_interrupted: { fa: 'ارتباط در میانهٔ پاسخ قطع شد. دوباره تلاش کنید.', en: 'The connection dropped in the middle of the answer. Try again.' },
};

const COMMON: Messages = {
  vector_store_unavailable: { fa: 'پایگاه بردار (Qdrant) در دسترس نیست. سرویس را بررسی کنید.', en: 'The vector database (Qdrant) is unavailable. Check the service.' },
  busy: { fa: 'سرویس مشغول کار دیگری است. چند لحظه بعد دوباره تلاش کنید.', en: 'The service is busy. Try again in a moment.' },
  not_ready: { fa: 'مدل‌ها هنوز در حال آماده‌شدن هستند. کمی صبر کنید.', en: 'Models are still loading. Please wait a moment.' },
  internal_error: { fa: 'خطای داخلی سرویس رخ داد. گزارش‌ها را بررسی کنید.', en: 'An internal service error occurred. Check the logs.' },
  network: { fa: 'ارتباط با سرویس برقرار نشد. اجرای برنامه و اتصال را بررسی کنید.', en: 'Could not reach the service. Check that it is running.' },
};

const NOTICES: Messages = {
  ocr_page_limit: { fa: 'فقط صفحه‌های اسکن‌شدهٔ اول خوانده شد (سقف OCR).', en: 'Only the first scanned pages were read (OCR limit).' },
  ocr_image_limit: { fa: 'متن برخی تصویرها خوانده نشد (سقف OCR تصویر).', en: 'Some images were not read (OCR image limit).' },
  ocr_partial: { fa: 'OCR بخشی از صفحه‌ها یا تصویرها را نتوانست بخواند.', en: 'OCR could not read some pages or images.' },
};

/** Translate an API error code for an upload, or undefined when unknown. */
export function uploadErrorMessage(code: string | undefined, language: Language): string | undefined {
  const entry = code ? UPLOAD[code] ?? COMMON[code] : undefined;
  return entry?.[language];
}

/** Translate an API error code for a question, or undefined when unknown. */
export function queryErrorMessage(code: string | undefined, language: Language): string | undefined {
  const entry = code ? QUERY[code] ?? COMMON[code] : undefined;
  return entry?.[language];
}

/** Translate a partial-indexing notice code. */
export function noticeMessage(code: string, language: Language): string {
  return NOTICES[code]?.[language] ?? code;
}
