[
  {
    "insertId": "682ffc25000892f49896706a",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1355",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.142",
      "serverIp": "216.239.36.54",
      "latency": "0.015613718s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "service_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis",
        "configuration_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T04:40:05.534537Z",
    "severity": "ERROR",
    "labels": {
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-managed-by": "cloudfunctions",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/28aa953fa1f2991be95301717a3e65bc",
    "receiveTimestamp": "2025-05-23T04:40:05.567785272Z",
    "spanId": "5024fe1f77957d35",
    "traceSampled": true
  },
  {
    "insertId": "1f254dkf7qk7h7",
    "jsonPayload": {
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "targetType": "HTTP",
      "status": "INTERNAL",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "job_id": "crypto-signal-generation-job",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T04:40:05.574339854Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T04:40:05.574339854Z"
  },
  {
    "insertId": "682ffd4d0009c5efbc9210ce",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.39",
      "serverIp": "216.239.36.54",
      "latency": "0.003398874s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "revision_name": "run-signal-generation-00056-tis",
        "service_name": "run-signal-generation",
        "location": "us-central1",
        "configuration_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T04:45:01.627191Z",
    "severity": "ERROR",
    "labels": {
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-managed-by": "cloudfunctions"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/af59c4d3c2ff05b301b72d804769039d",
    "receiveTimestamp": "2025-05-23T04:45:01.647247483Z",
    "spanId": "8074a7c223b58386",
    "traceSampled": true
  },
  {
    "insertId": "mh5y0me9p6xu",
    "jsonPayload": {
      "status": "INTERNAL",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "targetType": "HTTP",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "job_id": "crypto-signal-generation-job",
        "project_id": "telegram-signals-205cc",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T04:45:01.650852751Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T04:45:01.650852751Z"
  },
  {
    "insertId": "682ffe79000b04da5d744439",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.187.132.231",
      "serverIp": "216.239.36.54",
      "latency": "0.003591387s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "project_id": "telegram-signals-205cc",
        "revision_name": "run-signal-generation-00056-tis",
        "service_name": "run-signal-generation",
        "configuration_name": "run-signal-generation"
      }
    },
    "timestamp": "2025-05-23T04:50:01.705787Z",
    "severity": "ERROR",
    "labels": {
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-managed-by": "cloudfunctions",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-location": "us-central1"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/ed0c0508f16aef7fd9708da438a7a396",
    "receiveTimestamp": "2025-05-23T04:50:01.731384059Z",
    "spanId": "14abb9569474dddd",
    "traceSampled": true
  },
  {
    "insertId": "1bh6rxdf7fr2o4",
    "jsonPayload": {
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "targetType": "HTTP",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "status": "INTERNAL",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "location": "us-central1",
        "project_id": "telegram-signals-205cc",
        "job_id": "crypto-signal-generation-job"
      }
    },
    "timestamp": "2025-05-23T04:50:01.732669633Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T04:50:01.732669633Z"
  },
  {
    "insertId": "682fffa9000c2ce3b21363a3",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1355",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "34.116.39.103",
      "serverIp": "216.239.36.54",
      "latency": "0.003633254s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "revision_name": "run-signal-generation-00056-tis",
        "configuration_name": "run-signal-generation",
        "service_name": "run-signal-generation",
        "location": "us-central1",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T04:55:05.785410Z",
    "severity": "ERROR",
    "labels": {
      "goog-managed-by": "cloudfunctions",
      "goog-drz-cloudfunctions-location": "us-central1",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-id": "run_signal_generation"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/6d2cf7894b377f73d6745f34a4206e96",
    "receiveTimestamp": "2025-05-23T04:55:05.804070609Z",
    "spanId": "69de2c0f16d50cb6",
    "traceSampled": true
  },
  {
    "insertId": "95uqgtf6sam2d",
    "jsonPayload": {
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "status": "INTERNAL",
      "targetType": "HTTP"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "job_id": "crypto-signal-generation-job",
        "project_id": "telegram-signals-205cc",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T04:55:05.810791573Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T04:55:05.810791573Z"
  },
  {
    "insertId": "683000d1000d4e7973d66ace",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "107.178.194.73",
      "serverIp": "216.239.36.54",
      "latency": "0.004049940s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "service_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis",
        "configuration_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:00:01.857790Z",
    "severity": "ERROR",
    "labels": {
      "goog-managed-by": "cloudfunctions",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-drz-cloudfunctions-location": "us-central1"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/fedf931243cf10d90e46b97eacb2adce",
    "receiveTimestamp": "2025-05-23T05:00:01.879488772Z",
    "spanId": "dc6fc99211a64eca",
    "traceSampled": true
  },
  {
    "insertId": "1di8hf775x5k",
    "jsonPayload": {
      "status": "INTERNAL",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "targetType": "HTTP"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "job_id": "crypto-signal-generation-job",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T05:00:01.883686828Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:00:01.883686828Z"
  },
  {
    "insertId": "68300201000e87502e52445e",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1355",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.225",
      "serverIp": "216.239.36.54",
      "latency": "0.003226563s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "service_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc",
        "configuration_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis"
      }
    },
    "timestamp": "2025-05-23T05:05:05.940339Z",
    "severity": "ERROR",
    "labels": {
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-drz-cloudfunctions-location": "us-central1",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-managed-by": "cloudfunctions"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/03d7ea0ec6679397a57aa34b6a51284d",
    "receiveTimestamp": "2025-05-23T05:05:05.959504819Z",
    "spanId": "c3853af51df41119",
    "traceSampled": true
  },
  {
    "insertId": "1f2j711f7faktd",
    "jsonPayload": {
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "targetType": "HTTP",
      "status": "INTERNAL",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "location": "us-central1",
        "job_id": "crypto-signal-generation-job",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:05:05.962813903Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:05:05.962813903Z"
  },
  {
    "insertId": "6830032e0000bfb2965b2c81",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1355",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.235",
      "serverIp": "216.239.36.54",
      "latency": "0.003171199s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "configuration_name": "run-signal-generation",
        "service_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T05:10:06.037789Z",
    "severity": "ERROR",
    "labels": {
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-managed-by": "cloudfunctions"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/d4ab23338a35cb64b920f7d85d04e2c9",
    "receiveTimestamp": "2025-05-23T05:10:06.057602300Z",
    "spanId": "9c9cedb32352c470",
    "traceSampled": true
  },
  {
    "insertId": "1j7s1unf7bnmgg",
    "jsonPayload": {
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "targetType": "HTTP",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "status": "INTERNAL"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "location": "us-central1",
        "job_id": "crypto-signal-generation-job"
      }
    },
    "timestamp": "2025-05-23T05:10:06.062879795Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:10:06.062879795Z"
  },
  {
    "insertId": "683004550001dad96dfb7792",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.225",
      "serverIp": "216.239.36.54",
      "latency": "0.004182859s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "project_id": "telegram-signals-205cc",
        "configuration_name": "run-signal-generation",
        "service_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis"
      }
    },
    "timestamp": "2025-05-23T05:15:01.108655Z",
    "severity": "ERROR",
    "labels": {
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-managed-by": "cloudfunctions",
      "goog-drz-cloudfunctions-id": "run_signal_generation"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/81afffce5616f999a5c55960a2336e39",
    "receiveTimestamp": "2025-05-23T05:15:01.127737247Z",
    "spanId": "e2b30aa46972cafc",
    "traceSampled": true
  },
  {
    "insertId": "yylqfjf73hhx3",
    "jsonPayload": {
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "targetType": "HTTP",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "status": "INTERNAL",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "job_id": "crypto-signal-generation-job",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T05:15:01.133481524Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:15:01.133481524Z"
  },
  {
    "insertId": "683005810002f3719c402cef",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "107.178.194.193",
      "serverIp": "216.239.36.54",
      "latency": "0.003446345s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "service_name": "run-signal-generation",
        "configuration_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc",
        "revision_name": "run-signal-generation-00056-tis"
      }
    },
    "timestamp": "2025-05-23T05:20:01.182457Z",
    "severity": "ERROR",
    "labels": {
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-managed-by": "cloudfunctions",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/b8033c69aeb69d22b21881a0d41193e7",
    "receiveTimestamp": "2025-05-23T05:20:01.200080396Z",
    "spanId": "9593ba21e05ba954",
    "traceSampled": true
  },
  {
    "insertId": "166kvtzf39g56i",
    "jsonPayload": {
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "targetType": "HTTP",
      "status": "INTERNAL",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "job_id": "crypto-signal-generation-job",
        "location": "us-central1",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:20:01.205594212Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:20:01.205594212Z"
  },
  {
    "insertId": "683006b10004371a734b01b7",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1354",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "34.98.143.45",
      "serverIp": "216.239.36.54",
      "latency": "0.003552164s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "location": "us-central1",
        "configuration_name": "run-signal-generation",
        "revision_name": "run-signal-generation-00056-tis",
        "service_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:25:05.263799Z",
    "severity": "ERROR",
    "labels": {
      "goog-managed-by": "cloudfunctions",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-drz-cloudfunctions-id": "run_signal_generation",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/ba42a3472cc0b4009465c54cf8069195",
    "receiveTimestamp": "2025-05-23T05:25:05.282325893Z",
    "spanId": "12a6aa7f0b359a52",
    "traceSampled": true
  },
  {
    "insertId": "wrf156f7pdbhf",
    "jsonPayload": {
      "targetType": "HTTP",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "status": "INTERNAL",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "project_id": "telegram-signals-205cc",
        "location": "us-central1",
        "job_id": "crypto-signal-generation-job"
      }
    },
    "timestamp": "2025-05-23T05:25:05.287870282Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:25:05.287870282Z"
  },
  {
    "insertId": "683007dd00056fd3167d1067",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1353",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "35.243.23.238",
      "serverIp": "216.239.36.54",
      "latency": "0.002852350s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "revision_name": "run-signal-generation-00056-tis",
        "configuration_name": "run-signal-generation",
        "location": "us-central1",
        "service_name": "run-signal-generation",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:30:05.344552Z",
    "severity": "ERROR",
    "labels": {
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-managed-by": "cloudfunctions",
      "goog-drz-cloudfunctions-id": "run_signal_generation"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/7f9778e8f9041cbce3c5a2d20459d3d2",
    "receiveTimestamp": "2025-05-23T05:30:05.361618839Z",
    "spanId": "60334506285688e3",
    "traceSampled": true
  },
  {
    "insertId": "1acz1podijyu",
    "jsonPayload": {
      "targetType": "HTTP",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "status": "INTERNAL"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "job_id": "crypto-signal-generation-job",
        "project_id": "telegram-signals-205cc",
        "location": "us-central1"
      }
    },
    "timestamp": "2025-05-23T05:30:05.371580712Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:30:05.371580712Z"
  },
  {
    "insertId": "683009050006975f93a0902c",
    "httpRequest": {
      "requestMethod": "POST",
      "requestUrl": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "requestSize": "1355",
      "status": 500,
      "responseSize": "172",
      "userAgent": "Google-Cloud-Scheduler",
      "remoteIp": "34.98.143.34",
      "serverIp": "216.239.36.54",
      "latency": "0.003017389s",
      "protocol": "HTTP/1.1"
    },
    "resource": {
      "type": "cloud_run_revision",
      "labels": {
        "configuration_name": "run-signal-generation",
        "location": "us-central1",
        "project_id": "telegram-signals-205cc",
        "revision_name": "run-signal-generation-00056-tis",
        "service_name": "run-signal-generation"
      }
    },
    "timestamp": "2025-05-23T05:35:01.418445Z",
    "severity": "ERROR",
    "labels": {
      "goog-managed-by": "cloudfunctions",
      "instanceId": "007f65c6d2616073aceb0927fcc633396fa7527cc81265ca6fcc6edd48b503101267cfa70b576db4c70c18586a6ccbe49af588268607ee12ffe126d5898f2cec4f500e375f26b810c374b4ac313b76",
      "goog-drz-cloudfunctions-location": "us-central1",
      "goog-drz-cloudfunctions-id": "run_signal_generation"
    },
    "logName": "projects/telegram-signals-205cc/logs/run.googleapis.com%2Frequests",
    "trace": "projects/telegram-signals-205cc/traces/3152c70c154c864cea072c3d46e193f2",
    "receiveTimestamp": "2025-05-23T05:35:01.441799326Z",
    "spanId": "b55e0e8e8859a91c",
    "traceSampled": true
  },
  {
    "insertId": "q4lq82f7axvqt",
    "jsonPayload": {
      "targetType": "HTTP",
      "jobName": "projects/telegram-signals-205cc/locations/us-central1/jobs/crypto-signal-generation-job",
      "url": "https://us-central1-telegram-signals-205cc.cloudfunctions.net/run_signal_generation",
      "status": "INTERNAL",
      "@type": "type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished",
      "debugInfo": "URL_UNREACHABLE-UNREACHABLE_5xx. Original HTTP response code number = 500"
    },
    "httpRequest": {
      "status": 500
    },
    "resource": {
      "type": "cloud_scheduler_job",
      "labels": {
        "job_id": "crypto-signal-generation-job",
        "location": "us-central1",
        "project_id": "telegram-signals-205cc"
      }
    },
    "timestamp": "2025-05-23T05:35:01.443538970Z",
    "severity": "ERROR",
    "logName": "projects/telegram-signals-205cc/logs/cloudscheduler.googleapis.com%2Fexecutions",
    "receiveTimestamp": "2025-05-23T05:35:01.443538970Z"
  }
]