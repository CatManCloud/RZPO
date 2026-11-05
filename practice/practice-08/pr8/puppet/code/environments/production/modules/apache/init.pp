class apache {
  package { 'apache2':
    ensure => installed,
  }

  service { 'apache2':
    ensure   => running,
    enable   => true,
    provider => 'debian',
    require  => Package['apache2'],
  }

  file { '/var/www/html/index.html':
    content => '<html><body><h1>Deployed by Puppet</h1></body></html>',
    require => Package['apache2'],
  }
}