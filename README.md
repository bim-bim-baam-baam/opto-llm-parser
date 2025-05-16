## TODO
1) сохранять результаты в бд и кэшировать, чтобы ускорить. Если появились новые результаты, то только тогда добавляем в бд, иначе берем оттуда. Проиндексировать бд.
2) От Кирилла получать еще настоящий path
3) Возможно стоит получить (тоже дипсиком) конечное количество error_type и уже размечивать дипсиком. Но звучит сложнее.
4) Сделать API для Вани и Султана с возвращением этого JSON

------
## 0:24, 17.05.2025

Жюри сделали большой акцент на производительности, и она реально будет решающей.  

Сейчас user story выглядит так:  
1) Пользователь обращается к приложению к его API по HTTP-запросу например /results
2) Я паршу этот запрос и обращаюсь к своему редису. Если flag **IS_UPDATED_LATEST_LOGS** == False (об этом чуть позже),
то ищем данные в кэше в редисе. Если они там есть, то их и возвращаем
(либо делаем с ними запрос к сервису с моделькой Вани и Султана и возвращаем более точные результаты)
Если их в кеше нет, то кладем в кеш из бд и тоже самое.
3) Если флаг **IS_UPDATED_LATEST_LOGS** == True, это значит, что у базальта обновилась папка latest и нужно также обновить содержимое моего бд.
Пока флаг True мы замораживаемся на этом моменте и ждём. В этот момент сервис Кирилла проверяет что обновилось а что осталось прежним, чтобы закинуть только новые логи. 
Однако старые какие-то могли быть исправлены и исчезли - это тоже придется проверять. Короче гемор и возможно проще пока что просто заново сканить /latest.
Дальше Кирилл выдает мне эти .txt файлы (тут тоже проблема - мне бы как-то их разом получить, либо получить сообщение, что мол обработка завершена, иначе не понятно сколько таких файлов еще ждать)
теперь я их обрабатываю дипсиком и когда все обработаю, то флагIS_UPDATED_LATEST_LOGS ставлю False и размораживаю тот вызов функции
4) Дальше функция вернет тот json формата:  
```json
[
  {
    "path": "https://git.altlinux.org/beehive/logs/Sisyphus/i586/latest/error/android-file-transfer-4.2-alt1_2",
    "package": "android-file-transfer",
    "error_type": "cmake_minimum_required",
    "programming_language": "C++",
    "description": "CMake configuration error: cmake_minimum_required specifies a version below 3.5, which is no longer supported. Update to a compatible CMake version."
  },
  {
    "path": "https://git.altlinux.org/beehive/logs/Sisyphus/i586/latest/error/apache2-mod_perl-2.0.13-alt1",
    "package": "apache2-mod_perl",
    "error_type": "compilation,pointer_mismatch",
    "programming_language": "C",
    "description": "Compilation error due to incompatible function pointer types during initialization (svt_copy). Likely caused by API changes or incorrect function signatures in Perl/mod_perl integration."
  }
]

```