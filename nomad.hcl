job "md-uvdoc" {
  type = "service"

  group "MD-UVDoc" {
    count = 1

    restart {
      attempts = 2
      interval = "5m"
      delay    = "15s"
      mode     = "fail"
    }

    reschedule {
      attempts       = 2
      interval       = "10m"
      delay          = "30s"
      delay_function = "constant"
      unlimited      = false
    }

    network {
      port "node" {
        to = 9006
      }
    }

    service {
      name     = "md-uvdoc"
      port     = "node"
      provider = "nomad"
      
      check {
        type     = "http"
        path     = "/health"
        interval = "10s"
        timeout  = "3s"
      }
    }

    task "md-uvdoc" {
      driver = "podman"
      config {
          image = "localhost/messydesk/md-uvdoc:0.2"
          force_pull = false
          ports = ["node"]
          # Disk mode: the service reads and writes MessyDesk's data directory. Adjust the host paths.
          volumes = [
            "/srv/messydesk:/md",
          ]
      }
      env {
        PORT = "9006"
        MD_PATH = "/md"
      }
      resources {
        memory = 2000  # Memory in MB
        cpu    = 500  # CPU shares (500 = 50% of 1 CPU)
      }
    }
  }
}