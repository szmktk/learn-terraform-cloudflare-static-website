---
title: "Host a static website with S3 and Cloudflare | Terraform"
source: "https://web.archive.org/web/20250327200148/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website"
author:
published:
created: 2026-07-27
description: "Set up an S3-hosted static website with Cloudflare for DNS, TLS, and CDN. Redirect HTTP traffic to HTTPS, and redirect certain paths with Cloudflare page rules. Alternatively, use ACM for TLS certificate management and Cloudfront for CDN."
tags:
  - "clippings"
---
Cloudflare is a popular service that offers a Content Delivery Network (CDN), Domain Name System (DNS), and protection against Distributed Denial of Service (DDoS) attacks. The Terraform Cloudflare provider allows you to deploy and manage your content distribution services with the same workflow you use to manage infrastructure. Using Terraform, you can provision DNS records and distribution rules for your web applications hosted in AWS and other cloud services, as well as the underlying infrastructure hosting your services.

In this tutorial, you will deploy a static website using the AWS and Cloudflare providers. The site will use AWS to provision an S3 bucket for object storage and Cloudflare for DNS, [TLS](https://web.archive.org/web/20250327200148mp_/https://www.cloudflare.com/ssl/) and [CDN](https://web.archive.org/web/20250327200148mp_/https://www.cloudflare.com/cdn/). Then, you will add Cloudflare [page rules](https://web.archive.org/web/20250327200148mp_/https://support.cloudflare.com/hc/en-us/articles/218411427-Understanding-and-Configuring-Cloudflare-Page-Rules-Page-Rules-Tutorial-) to always redirect HTTP requests to HTTPS and to temporarily redirect users when they visit a specific page.

![This diagram shows how users interact with CloudFlare and S3 bucket](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fstatic-website-service-diagram.png&width=792&height=320)

This diagram shows how users interact with CloudFlare and S3 bucket

This tutorial offers two options for CDN:

- **Cloudflare** - The simplest option is to use Cloudflare's native TLS and CDN, included in its [free tier](https://web.archive.org/web/20250327200148mp_/https://www.cloudflare.com/plans/). If you use Cloudflare for DNS, Cloudflare's included TLS and CDN services let you set up a secure, cached static website with just an S3 bucket. This workflow requires that your bucket name match your domain name.
- **AWS's ACM and CloudFront** - If you cannot create an S3 bucket matching your domain name, you can use ACM for TLS certificate management and CloudFront for CDN. Using both ACM and Cloudfront lets you secure and cache traffic to your S3 bucket.

Select your preferred CDN option above. If you are not sure which to pick, choose Cloudflare for ease of use.

## Prerequisites

This tutorial assumes that you are familiar with the standard Terraform workflow. If you are new to Terraform, complete the [Get Started tutorials](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/aws-get-started) first.

For this tutorial, you will need:

- the [Terraform CLI](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) 0.14+ installed locally
- an [AWS account](https://web.archive.org/web/20250327200148mp_/https://portal.aws.amazon.com/billing/signup?nc2=h_ct&src=default&redirect_url=https%3A%2F%2Faws.amazon.com%2Fregistration-confirmation#/start) with credentials [configured for Terraform](https://web.archive.org/web/20250327200148mp_/https://registry.terraform.io/providers/hashicorp/aws/latest/docs#authentication)
- a [Cloudflare account](https://web.archive.org/web/20250327200148mp_/https://support.cloudflare.com/hc/en-us/articles/201720164)
- a domain name with nameservers pointing to Cloudflare. Cloudflare needs to manage the domain's DNS records. You can either [register a new domain](https://web.archive.org/web/20250327200148mp_/https://www.cloudflare.com/products/registrar/) or [change an existing domain's nameserver to Cloudflare](https://web.archive.org/web/20250327200148mp_/https://support.cloudflare.com/hc/en-us/articles/205195708-Changing-your-domain-nameservers-to-Cloudflare).

Note

Some of the infrastructure in this tutorial may not qualify for the AWS [free tier](https://web.archive.org/web/20250327200148mp_/https://aws.amazon.com/free/). Destroy the infrastructure at the end of the guide to avoid unnecessary charges. We are not responsible for any charges that you incur.

## Create a scoped Cloudflare API token

There are several ways to authenticate the Terraform Cloudflare provider. In this tutorial, you will use a Cloudflare API token. This method grants granular control of token permissions, keeps the token out of version control, and allows you to revoke the token when necessary.

This tutorial requires a Cloudflare API token with "Edit" permissions for your zone's **DNS** and **Page Rules**. If you would like to use an existing Cloudflare API token that already has these permissions, you can go to the [Clone the example repository](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website#clone-the-example-repository) section.

To create an API token, go to the [**API Tokens**](https://web.archive.org/web/20250327200148mp_/https://dash.cloudflare.com/profile/api-tokens) page for your Cloudflare account. You can access this page by clicking on the user icon on the top right corner > **My Profile** > **API Tokens**.

Click on **Create Token**.

![Cloudflare API token page](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fcloudflare-api-token-page.png&width=2048&height=836)

Cloudflare API token page

Find the **Create Custom Token** option, then click **Get Started**.

![Cloudflare create custom API token](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fcreate-custom-api-token.png&width=2048&height=909)

Cloudflare create custom API token

On the **Create Custom Token** page, modify the following fields:

1. In **Token name**, enter `Terraform Token`.
2. In the **Permissions** section, grant the API token permission to edit your zone's DNS and page rules:
	1. Set the first permission to **Zone**, **DNS**, and **Edit**.
		2. Add a second permission, and set it to **Zone**, **Page Rules**, and **Edit**.
3. In the **Zone Resources** section, select **Include**, **Specific zone**, and the domain you want to manage with Cloudflare.

This page should look like the following, with your domain name instead of `hashicorp.fun` in the **Zone Resources** section.

![Cloudflare custom API token settings](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fcustom-api-token-settings.png&width=2048&height=1391)

Cloudflare custom API token settings

Click **Continue to summary**, then **Create Token** to create your scoped Cloudflare API token.

![Cloudflare custom API token confirmation page](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fcustom-api-token-confirmation.png&width=2048&height=883)

Cloudflare custom API token confirmation page

Cloudflare only displays your API token once. Record it somewhere safe. You will use this token to authenticate the Cloudflare provider.

![Cloudflare custom API token](https://web.archive.org/web/20250327200148im_/https://content.hashicorp.com/api/assets?product=tutorials&version=main&asset=public%2Fimg%2Fterraform%2Fuse-cases%2Fcloudflare-static-website%2Fcustom-api-token-created.png&width=2048&height=601)

Cloudflare custom API token

Create an environment variable named [`CLOUDFLARE_API_TOKEN`](https://web.archive.org/web/20250327200148mp_/https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs#api_token) and set it to your Cloudflare API token.

```
$ export CLOUDFLARE_API_TOKEN=
```

Terraform will reference this environment variable to authenticate the Cloudflare Provider. Using an environment variable prevents you from accidentally committing your token to version control.

## Clone the example repository

Clone the [example repository](https://web.archive.org/web/20250327200148mp_/https://github.com/hashicorp-education/learn-terraform-cloudflare-static-website) for this tutorial, which contains Terraform configuration for an S3 bucket and Cloudflare DNS records. The next section reviews each resource's configuration.

```
$ git clone https://github.com/hashicorp-education/learn-terraform-cloudflare-static-website
```

Change into the repository directory.

```
$ cd learn-terraform-cloudflare-static-website
```

## Review configuration

In this section, you will review the files and Terraform resource definitions in the example repository. If you want to jump ahead to provisioning the resources, you can go to the [Modify variables](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website#modify-variables) section and use this section as a reference later.

change into the `cloudflare` subdirectory.

```
$ cd cloudflare
```

this configuration contains the following files:

- the **`main.tf`** file contains configuration to provision the s3 bucket and update your cloudflare dns records.
- the **`outputs.tf`** file defines outputs that display your s3 bucket name, bucket endpoint, and domain name.
- the **`terraform.tf`** file contains `terraform` block definition, including the `required_providers` block that specifies which provider versions to use.
- the **`variables.tf`** file contains the input variable declarations, including the aws region and website domain name.
- the **`terraform.tfvars.example`** file is an example variable definition file. later in this tutorial, you will copy this file and modify it to include your aws region and domain name.
- the **`/website`** directory contains [terramino](https://web.archive.org/web/20250327200148mp_/https://github.com/hashicorp-education/learn-terramino), a demo website containing a hashicorp-skinned tetris game. this directory is located in this repository to simplify this tutorial. ordinarily you should not store your static website in the same directory as your terraform configuration.
- the **`terraform.lock.hcl`** file ensures that [terraform uses the same provider versions for each run](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/configuration-language/provider-versioning).

open the `main.tf` file in your editor to review the configuration.

- the aws provider block [authenticates](https://web.archive.org/web/20250327200148mp_/https://registry.terraform.io/providers/hashicorp/aws/latest/docs#authentication) to aws, scoped to the region specified by the `aws_region` input variable. the cloudflare provider authenticates using the scoped api token you created in the [prerequisites](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website#create-a-scoped-cloudflare-api-token), accessed by an environment variable.
	```hcl
	provider "aws" {
	  region = var.aws_region
	}
	provider "cloudflare" {}
	```
- The `aws_s3_bucket.site`, `aws_s3_bucket_public_access_block.site`, `aws_s3_bucket_website_configuration.site`,`aws_s3_bucket_ownership_controls.site`, `aws_s3_bucket_acl.site`, and `aws_s3_bucket_policy.site` resources create a new S3 bucket and set it to be publicly readable. This policy allows anyone to view your static website.
	```hcl
	resource "aws_s3_bucket" "site" {
	  bucket = var.site_domain
	}
	resource "aws_s3_bucket_public_access_block" "site" {
	  bucket = aws_s3_bucket.site.id
	  block_public_acls       = false
	  block_public_policy     = false
	  ignore_public_acls      = false
	  restrict_public_buckets = false
	}
	resource "aws_s3_bucket_website_configuration" "site" {
	  bucket = aws_s3_bucket.site.id
	  index_document {
	  suffix = "index.html"
	  }
	  error_document {
	  key = "error.html"
	  }
	}
	resource "aws_s3_bucket_ownership_controls" "site" {
	  bucket = aws_s3_bucket.site.id
	  rule {
	  object_ownership = "BucketOwnerPreferred"
	  }
	}
	resource "aws_s3_bucket_acl" "site" {
	  bucket = aws_s3_bucket.site.id
	  acl = "public-read"
	  depends_on = [
	  aws_s3_bucket_ownership_controls.site,
	  aws_s3_bucket_public_access_block.site
	  ]
	}
	resource "aws_s3_bucket_policy" "site" {
	  bucket = aws_s3_bucket.site.id
	  policy = jsonencode({
	  Version = "2012-10-17"
	  Statement = [
	    {
	    Sid       = "PublicReadGetObject"
	    Effect    = "Allow"
	    Principal = "*"
	    Action    = "s3:GetObject"
	    Resource = [
	      aws_s3_bucket.site.arn,
	      "${aws_s3_bucket.site.arn}/*",
	    ]
	    },
	  ]
	  })
	  depends_on = [
	  aws_s3_bucket_public_access_block.site
	  ]
	}
	```
	Note that the bucket name references your domain. To use Cloudflare for TLS and DNS, the bucket name and domain must match.
	Tip
	In this tutorial, the S3 bucket policy is set to public-read. When creating an S3 bucket, create the appropriate policy for your bucket.
- The `cloudflare_zones.domain` data source retrieves your Cloudflare zone ID. The Cloudflare resources in this configuration will use this value to apply changes to your zone.
	```hcl
	data "cloudflare_zones" "domain" {
	  filter {
	    name = var.site_domain
	  }
	}
	```
- Finally, the `cloudflare_record.site_cname` and `cloudflare_record.www` resources create a Cloudflare CNAME record that points to the CloudFront distribution domain name.
	Notice that both records have `proxied` set to `true`, which routes your site traffic through Cloudflare's proxy. This enables you to use CloudFlare page rules and DDoS protection features.
	```hcl
	resource "cloudflare_record" "site_cname" {
	  zone_id = data.cloudflare_zones.domain.zones[0].id
	  name    = var.site_domain
	  value   = aws_s3_bucket_website_configuration.site.website_endpoint
	  type    = "CNAME"
	  ttl     = 1
	  proxied = true
	}
	resource "cloudflare_record" "www" {
	  zone_id = data.cloudflare_zones.domain.zones[0].id
	  name    = "www"
	  value   = var.site_domain
	  type    = "CNAME"
	  ttl     = 1
	  proxied = true
	}
	```

## Set variable values

Copy the contents of `terraform.tfvars.example` into a new file named `terraform.tfvars`.

```
$ cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` and update the value of `site_domain` to your own domain.

```
aws_region         = "us-east-1"
site_domain        = "YOUR.DOMAIN"
```

Warning

Never commit sensitive values into source control. The `.gitignore` file found in this repo ignores the `terraform.tfvars` file. Always include a `.gitignore` file in your own Terraform repositories.

## Apply configuration

Initialize the Terraform configuration.

```
$ terraform init

Initializing the backend...

Initializing provider plugins...
- Reusing previous version of hashicorp/random from the dependency lock file
- Reusing previous version of hashicorp/aws from the dependency lock file
- Reusing previous version of cloudflare/cloudflare from the dependency lock file
- Installing hashicorp/aws v4.0.0...
- Installed hashicorp/aws v4.0.0 (signed by HashiCorp)
- Installing cloudflare/cloudflare v2.19.2...
- Installed cloudflare/cloudflare v2.19.2 (signed by a HashiCorp partner, key ID DE413CEC881C3283)
- Installing hashicorp/random v3.1.0...
- Installed hashicorp/random v3.1.0 (signed by HashiCorp)

Partner and community providers are signed by their developers.
If you'd like to know more about provider signing, you can read about it here:
https://web.archive.org/web/20250327200148/https://www.terraform.io/docs/cli/plugins/signing.html

Terraform has been successfully initialized!

You may now begin working with Terraform. Try running "terraform plan" to see
any changes that are required for your infrastructure. All Terraform commands
should now work.

If you ever set or change modules or backend configuration for Terraform,
rerun this command to reinitialize your working directory. If you forget, other
commands will detect it and remind you to do so if necessary.
```

Next, apply the configuration. Respond `yes` to the prompt to confirm.

Note

If you encounter a duplicate name error while creating the S3 bucket, [destroy the provisioned resources](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website#clean-up-resources), then select the "ACM and CloudFront tab" in the [Review configuration](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/applications/cloudflare-static-website#review-configuration) section and follow the steps to re-provision.

```
$ terraform apply

## ...
Plan: 8 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_endpoint     = (known after apply)
  + domain_name         = "your.domain"
  + website_bucket_name = (known after apply)

Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes
##...
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:

bucket_endpoint = "your.domain.s3-website-us-east-1.amazonaws.com"
domain_name = "your.domain"
website_bucket_name = "your.domain"
```

## Add website files to S3 bucket

Now that you have set up the static website, upload the contents in the `/website` directory to your newly provisioned S3 bucket. Notice that the following command retrieves the bucket name from Terraform output.

```
$ aws s3 cp website/ s3://$(terraform output -raw website_bucket_name)/ --recursive
upload: website/index.html to s3://turkey-hashicorp.fun/index.html
upload: website/background.png to s3://turkey-hashicorp.fun/background.png
```

Navigate to your website in your web browser. Your Terramino app should start automatically.

## Create Cloudflare page rules

Cloudflare has page rules that trigger actions whenever the page URL matches a specified URL pattern. You can use page rules to forward URLs, configure security and cache levels, and enforce HTTPS. Refer to [Cloudflare's recommended page rules](https://web.archive.org/web/20250327200148mp_/https://www.cloudflare.com/features-page-rules/must-use-page-rules/) for more use cases.

First, add a page rule to the `main.tf` file enforce TLS by redirecting any `http://` request to `https://`.

```hcl
resource "cloudflare_page_rule" "https" {
  zone_id = data.cloudflare_zones.domain.zones[0].id
  target  = "*.${var.site_domain}/*"
  actions {
    always_use_https = true
  }
}
```

Next, add another page rule to the `main.tf` file to temporarily redirect `<your-domain>/learn` to the Terraform developer portal, where `your-domain` is your domain name.

```hcl
resource "cloudflare_page_rule" "redirect_to_terraform" {
  zone_id = data.cloudflare_zones.domain.zones[0].id
  target  = "${var.site_domain}/learn"
  actions {
    forwarding_url {
      status_code = 302
      url         = "https://developer.hashicorp.com/terraform"
    }
  }
}
```

Apply these changes. Respond `yes` to the prompt to confirm.

```
$ terraform apply

## ...

cloudflare_page_rule.redirect_to_terraform: Creating...
cloudflare_page_rule.https: Creating...
cloudflare_page_rule.https: Creation complete after 1s [id=5681df98c982f0b5af15d5183756a487]
cloudflare_page_rule.redirect_to_terraform: Creation complete after 1s [id=c6be51ba9e52cb21ce9c7c8fd584bd22]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

bucket_endpoint = "your.domain.fun.s3-website-us-east-1.amazonaws.com"
domain_name = "your.domain"
website_bucket_name = "your.domain"
```

Verify these changes by visiting `https://web.archive.org/web/20250327200148/http://your-domain.com` and `https://web.archive.org/web/20250327200148/https://your-domain.com/learn`, where `your-domain` is your domain name. In the first instance, your browser should redirect you to the `https://` version of the website. In the second instance, your browser should redirect you to the [Terraform tutorials page](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials).

## Clean up resources

In this tutorial, you used Terraform to set up a TLS-secured static website with S3 and Cloudflare. You can choose to keep your website or destroy it.

You can repurpose this website to your needs by updating the contents of the S3 bucket

You may want to remove `cloudflare_page_rule.redirect_to_terraform`, which temporarily redirects `your-domain.com/learn` to the Terraform tutorials page. Remove the resource from `main.tf`.

```
- resource "cloudflare_page_rule" "redirect_to_terraform" {
-   zone_id = data.cloudflare_zones.domain.zones[0].id
-   target  = "${var.site_domain}/learn"
-   actions {
-     forwarding_url {
-       status_code = 302
-       url         = "https://learn.hashicorp.com/terraform"
-     }
-   }
- }
```

Apply these changes. Respond `yes` to the prompt to confirm.

```
$ terraform apply

## ...

Terraform will perform the following actions:

  # cloudflare_page_rule.https will be updated in-place
  ~ resource "cloudflare_page_rule" "https" {
        id       = "REDACTED"
      ~ priority = 2 -> 1
        # (3 unchanged attributes hidden)

        # (1 unchanged block hidden)
    }

  # cloudflare_page_rule.redirect_to_terraform will be destroyed
  - resource "cloudflare_page_rule" "redirect_to_terraform" {
      - id       = "REDACTED" -> null
      - priority = 1 -> null
      - status   = "active" -> null
      - target   = "hashicorp.fun/learn" -> null
      - zone_id  = "REDACTED" -> null

      - actions {
          - always_use_https    = false -> null
          - disable_apps        = false -> null
          - disable_performance = false -> null
          - disable_railgun     = false -> null
          - disable_security    = false -> null
          - edge_cache_ttl      = 0 -> null

          - forwarding_url {
              - status_code = 302 -> null
              - url         = "https://learn.hashicorp.com/terraform" -> null
            }
        }
    }

Plan: 0 to add, 1 to change, 1 to destroy.

## ...

cloudflare_page_rule.redirect_to_terraform: Destroying... [id=c6be51ba9e52cb21ce9c7c8fd584bd22]
cloudflare_page_rule.https: Modifying... [id=5681df98c982f0b5af15d5183756a487]
cloudflare_page_rule.redirect_to_terraform: Destruction complete after 0s
cloudflare_page_rule.https: Modifications complete after 1s [id=5681df98c982f0b5af15d5183756a487]

Apply complete! Resources: 0 added, 1 changed, 1 destroyed.

## ...
```

## Next steps

To learn more about managing the resources used in this tutorial with Terraform, visit the following documentation:

- The [Terraform Cloudflare Provider](https://web.archive.org/web/20250327200148mp_/https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs) Registry page contains documentation for Cloudflare resources, including arguments, attributes, and example configuration.
- The [Create IAM policies](https://web.archive.org/web/20250327200148mp_/https://developer.hashicorp.com/terraform/tutorials/aws/aws-iam-policy) tutorial guides you through creating differently scoped IAM policies for your AWS resources.
- The [Cloudflare-managed Terraform documentation](https://web.archive.org/web/20250327200148mp_/https://developers.cloudflare.com/terraform/) contains tutorials for topics such as using the Cloudflare provider to rate limit and load balance requests, importing existing Cloudflare resources, and customizing the provider.
- This [AWS Knowledge Center post](https://web.archive.org/web/20250327200148mp_/https://aws.amazon.com/premiumsupport/knowledge-center/cloudfront-serving-outdated-content-s3/) walks you through updating your CloudFront cache to reflect the latest changes to your S3 bucket.